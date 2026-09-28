from __future__ import annotations

import json
import re
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from wikipedia_retrieval_engine.retrievers.base import ArticleCandidate
from wikipedia_retrieval_engine.retrievers.corpus import MarkdownArticleStore
from wikipedia_retrieval_engine.retrievers.graph import GraphParams, WikiGraph
from wikipedia_retrieval_engine.retrievers.multistep import MultiStepRetriever
from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.utils.wiki_table_parser import NormalizedTable
from wikipedia_retrieval_engine.utils.wiki_table_store import (
    TableArtifactStore,
    TableCatalogEntry,
)
from wikipedia_retrieval_engine.wiki_agents.table_nodes import resolve_source_article
from wikipedia_retrieval_engine.wiki_agents.answer_context import (
    ArticleTextLoader,
    articles_to_send_whole,
    replace_with_whole_articles,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    ArticleReview,
    ArticleReviewBatch,
    EvidenceAssessment,
    EvidenceItem,
    RetrievalRequest,
    TableRequest,
    retrieval_attempt_count,
)

ARTICLE_REVIEW_SYSTEM_PROMPT = """
You are reviewing Wikipedia articles retrieved for a user's question.

For every candidate article:
- Decide whether its excerpt is relevant to the question.
- Use the exact source_article value provided.
- Explain why the article should be kept or rejected.
- Set needs_table_reader to true when the required facts appear to depend
  on comparing, filtering, or aggregating tabular data.
- Do not invent section or table names.
- Only populate relevant_sections or relevant_table_names when those names
  are explicitly identifiable from the provided excerpt.
- Return exactly one review for every candidate.
- Do not use outside knowledge.
""".strip()

TOC_REVIEW_SYSTEM_PROMPT = """
You choose which retrieved Wikipedia articles to use and which of their sections to read, for a user's question.

For each candidate article you are shown its title, its table of contents (section names), and a short list of the tables it contains. You are NOT shown section text — judge from the article's identity and its section list, not from a snippet.

Return exactly one review per candidate article:
- relevant: true if the article is a correct source for the question. Judge whether the article is on-topic and whether its sections could hold the needed facts. Do NOT reject an article just because no single section obviously answers the whole question.
- reason: one brief sentence.
- relevant_sections: the exact section names (copied from the table of contents) whose content should be read. Pick the sections that hold the needed facts (e.g. "Winners and nominees"), not overview, "See also", or reference sections. If the article is relevant, list at least one section.
- relevant_table_ids: stable Artifact ID values (copied exactly) for every listed
  table the question needs. Select every table needed for a multi-period or
  cross-table question.
- relevant_table_names: use only when a legacy table listing has no Artifact ID.
- needs_table_reader: true ONLY when answering requires COMPUTING over table rows — filtering rows by a numeric or date threshold, counting, aggregating (sum/min/max/average), sorting, or intersecting rows across tables. Set it FALSE when the answer is a single looked-up value, a quotation, a date, or prose, even if the article contains tables.

Rules:
- Copy source_article, section names, and table labels exactly; never invent or rename them.
- Keep an article that is the right source even if you are unsure which single section answers it — list the plausible sections.
- Do not use outside knowledge and do not answer the question.
""".strip()

EVIDENCE_ASSESSMENT_SYSTEM_PROMPT = """
You are the evidence-control node in a Wikipedia question-answering graph.

Decide whether the supplied evidence is sufficient to answer every part of the
user's question. Use only the supplied article reviews and evidence excerpts.

Rules:
- Set ready_to_answer to true only when every required fact is supported.
- Describe which requirements are supported and which are still missing.
- When facts may be in a table from a selected article, create a table_request.
- Copy source_article exactly from the supplied reviews or evidence when creating
  a table_request; do not invent or rename article identifiers.
- When a relevant table artifact ID is supplied, copy it into table_id. Create a
  separate table_request for each artifact needed by a multi-table question.
- Use table operations such as lookup, filter, aggregate, compare, sort, or
  timeline to describe the required table work.
- Questions requiring row filtering, numeric/date thresholds, counting,
  aggregation, comparison, or sorting are not ready merely because raw table rows
  are present. Request table computation unless a deterministic
  table_computation evidence item already supplies the required result. A simple
  single-value lookup you can read directly does not need a table_request.
- Keep each table_request MINIMAL: set only missing_fact, source_article, table_id,
  and operation. Do NOT fill row_filters, columns_needed, thresholds, or years —
  the table tool derives the exact predicates itself. Never put a number in
  row_filters.
- When another retrieval call is required, create a retrieval_request containing
  the missing fact, a focused query, useful keywords, and likely target articles.
- Do not create a table request merely because an article contains any table.
- If evidence conflicts, record the conflict and request what is needed to
  resolve it.
- Do not use outside knowledge and do not answer the question.
""".strip()

EvidenceRoute = Literal[
    "ready_to_answer",
    "need_table_reader",
    "need_more_evidence",
]


def retrieve_initial_articles(
    state: AgentState,
    retriever: VectorRetriever,
    *,
    top_k: int = 3,
) -> AgentState:
    """Find the initial article candidates for a question.

    ``top_k`` is the number of unique articles to seed. It is a parameter (not a
    hard-coded 3) so the benchmark can size the initial net to the question set;
    e.g. GT questions designate up to four articles.
    """

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    article_candidates = retriever.getArticlesTopK(question, k=top_k)

    return {
        "article_candidates": article_candidates,
        "retrieval_attempts": retrieval_attempt_count(state) + 1,
    }


def retrieve_initial_articles_decomposed(
    state: AgentState,
    retriever: VectorRetriever,
    multistep: MultiStepRetriever,
    *,
    top_k: int = 4,
    per_subquery_k: int = 2,
    max_candidates: int = 8,
    decompose_mode: Literal["subtopic", "entity"] = "subtopic",
) -> AgentState:
    """Initial article discovery via query decomposition.

    Reuses the multi-step retriever's decomposition to split the question into
    sub-queries, retrieves article candidates for each with the section-aware
    vector retriever, and merges them (best distance per article). Entities a
    single blunt question query buries — e.g. GT16's ``Barack_Obama`` — are then
    reliably surfaced. The full question is always included as one of the
    queries, so this stage's candidate set is a superset of the plain-vector
    stage and recall cannot regress.

    ``decompose_mode`` selects the decomposition style:

    - ``"subtopic"`` — the 4.1 decomposer's broader sub-topic queries.
    - ``"entity"`` — one clean full-name query per named/implied entity, which
      probes show retrieves the exact designated article at rank 1.
    """

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")
    if top_k < 1 or per_subquery_k < 1 or max_candidates < 1:
        raise ValueError("top_k, per_subquery_k, and max_candidates must be >= 1.")

    if decompose_mode == "entity":
        sub_queries, _reasoning = multistep.decompose_entities(question)
    else:
        sub_queries, _reasoning = multistep.decompose(question)
    queries = list(
        dict.fromkeys(
            [question, *(q.strip() for q in sub_queries if q.strip())]
        )
    )

    best_by_article: dict[str, ArticleCandidate] = {}
    for query in queries:
        k = top_k if query == question else per_subquery_k
        for candidate in retriever.getArticlesTopK(query, k=k):
            existing = best_by_article.get(candidate.source_article)
            if existing is None or candidate.raw_score < existing.raw_score:
                best_by_article[candidate.source_article] = candidate

    ranked = sorted(best_by_article.values(), key=lambda c: c.raw_score)
    article_candidates = [
        candidate.model_copy(update={"rank": index})
        for index, candidate in enumerate(ranked[:max_candidates], start=1)
    ]

    return {
        "article_candidates": article_candidates,
        "retrieval_attempts": retrieval_attempt_count(state) + 1,
    }


def article_review_update(review_batch: ArticleReviewBatch) -> AgentState:
    """Convert structured article reviews into a partial state update."""

    reviews = review_batch.reviews

    return {
        "article_reviews": reviews,
        "selected_articles": [
            review.source_article
            for review in reviews
            if review.relevant
        ],
        "rejected_articles": [
            review.source_article
            for review in reviews
            if not review.relevant
        ],
    }


def review_article_candidates(
    state: AgentState,
    llm: BaseChatModel,
) -> AgentState:
    """Review retrieved article candidates using structured LLM output."""

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")

    candidates = state.get("article_candidates", [])
    if not candidates:
        return article_review_update(ArticleReviewBatch())

    candidate_context = "\n\n".join(
        (
            f"Source article: {candidate.source_article}\n"
            f"Representative excerpt:\n"
            f"{candidate.representative_chunk or '(no excerpt available)'}"
        )
        for candidate in candidates
    )

    structured_reviewer = llm.with_structured_output(
        ArticleReviewBatch,
        method="function_calling",
    )

    result = structured_reviewer.invoke(
        [
            SystemMessage(content=ARTICLE_REVIEW_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Question:\n{question}\n\n"
                    f"Candidate articles:\n{candidate_context}"
                )
            ),
        ]
    )

    review_batch = (
        result
        if isinstance(result, ArticleReviewBatch)
        else ArticleReviewBatch.model_validate(result)
    )

    expected_sources = sorted(
        candidate.source_article
        for candidate in candidates
    )
    reviewed_sources = sorted(
        review.source_article
        for review in review_batch.reviews
    )
    if reviewed_sources != expected_sources:
        raise ValueError(
            "Article reviewer must return exactly one review for every "
            f"candidate. Expected {expected_sources}, received {reviewed_sources}."
        )

    return article_review_update(review_batch)


def collect_initial_evidence(state: AgentState) -> AgentState:
    """Promote selected articles' representative chunks to initial evidence."""

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")

    selected_articles = set(state.get("selected_articles", []))
    existing_evidence = state.get("evidence", [])
    evidence_by_id = {
        item.evidence_id: item
        for item in existing_evidence
    }

    for candidate in state.get("article_candidates", []):
        if candidate.source_article not in selected_articles:
            continue
        if not candidate.representative_chunk:
            continue

        evidence_id = (
            candidate.representative_chunk_id
            or f"{candidate.source_article}#initial-rank-{candidate.rank}"
        )
        evidence_by_id[evidence_id] = EvidenceItem(
            evidence_id=evidence_id,
            source_article=candidate.source_article,
            content=candidate.representative_chunk,
            title=candidate.section_title,
            section_path=candidate.section_path,
            retrieval_query=candidate.retrieval_query,
            retriever="vector",
            rank=candidate.rank,
            raw_score=candidate.raw_score,
            score_semantics=candidate.score_semantics,
            metadata={
                "retrieval_stage": "initial_article_retrieval",
                "discovered_by": candidate.discovered_by,
            },
        )

    return {"evidence": list(evidence_by_id.values())}


def _article_toc(
    markdown_store: MarkdownArticleStore, source: str
) -> tuple[list[str], list[str]]:
    """Return (section titles, table labels) for one article from its sidecar."""

    if not markdown_store.has_article(source):
        return [], []
    try:
        meta = markdown_store.load_metadata(source)
    except (OSError, ValueError):
        return [], []

    section_titles = [
        str(section.get("title", "")).strip()
        for section in (meta.get("sections") or [])
        if isinstance(section, dict) and str(section.get("title", "")).strip()
    ]
    table_labels: list[str] = []
    for index, table in enumerate(meta.get("tables") or [], start=1):
        if not isinstance(table, dict):
            continue
        caption = str(table.get("caption") or "").strip()
        if not caption:
            headers = table.get("headers") or []
            caption = (str(headers[0])[:60].strip() if headers else "") or "unlabeled"
        table_labels.append(f"Table {index}: {caption}")
    return section_titles, table_labels


def _table_tokens(value: str) -> set[str]:
    """Normalize small variations used when ranking table catalog metadata."""

    aliases = {
        "nominated": "nominate",
        "nomination": "nominate",
        "nominations": "nominate",
        "nominee": "nominate",
        "nominees": "nominate",
        "winning": "win",
        "winner": "win",
        "winners": "win",
        "won": "win",
    }
    tokens: set[str] = set()
    for token in re.findall(r"[a-z0-9]+", value.casefold()):
        if len(token) < 2:
            continue
        if re.fullmatch(r"\d{4}s", token):
            token = token[:-1]
        tokens.add(aliases.get(token, token))
    return tokens


def _table_catalog_label(entry: TableCatalogEntry) -> str:
    """Expose an immutable table identity plus enough metadata to select it."""

    section = " > ".join(entry.section_path) or "(no section)"
    caption = str(entry.caption or "").strip() or "(no caption)"
    columns = ", ".join(entry.columns) or "(no columns)"
    return (
        f"Artifact ID: {entry.artifact_id} | Table ID: {entry.table_id} | "
        f"Section: {section} | Caption: {caption} | Columns: {columns}"
    )


def _rank_table_catalog_for_question(
    catalog: list[TableCatalogEntry],
    question: str,
) -> list[TableCatalogEntry]:
    """Rank all table metadata before applying the prompt-size limit.

    Decade sections receive an additional range-aware score. This makes a
    question spanning 2000 through 2020 surface the 2000s, 2010s, and 2020s
    tables even when those tables have identical columns and no captions.
    """

    question_tokens = _table_tokens(question)
    years = [int(value) for value in re.findall(r"\b(?:18|19|20)\d{2}\b", question)]
    year_start = min(years) if years else None
    year_end = max(years) if years else None

    def score(entry: TableCatalogEntry) -> int:
        metadata = " ".join(
            [
                entry.caption or "",
                *entry.section_path,
                *entry.columns,
                *entry.legend_meanings,
            ]
        )
        value = len(question_tokens & _table_tokens(metadata))
        if year_start is not None and year_end is not None:
            for decade_text in re.findall(r"\b((?:18|19|20)\d{2})s\b", metadata):
                decade = int(decade_text)
                if decade <= year_end and decade + 9 >= year_start:
                    value += 10
        return value

    indexed = list(enumerate(catalog))
    indexed.sort(key=lambda item: (score(item[1]), -item[0]), reverse=True)
    return [entry for _, entry in indexed]


def _table_labels_for_review(
    *,
    source_article: str,
    question: str,
    sidecar_labels: list[str],
    table_store: TableArtifactStore | None,
    max_tables_listed: int,
) -> tuple[list[str], set[str]]:
    """Return ranked prompt labels and the artifact IDs offered to the model."""

    if max_tables_listed < 1:
        return [], set()

    if table_store is not None:
        try:
            catalog = list(table_store.list_tables(source_article))
        except (KeyError, OSError, TypeError, ValueError):
            catalog = []
        if catalog:
            ranked = _rank_table_catalog_for_question(catalog, question)
            offered = ranked[:max_tables_listed]
            return (
                [_table_catalog_label(entry) for entry in offered],
                {entry.artifact_id for entry in offered},
            )

    # Legacy sidecars have no stable table identity. Rank the complete list
    # before truncating rather than always exposing only its leading entries.
    question_tokens = _table_tokens(question)
    ranked_labels = sorted(
        enumerate(sidecar_labels),
        key=lambda item: (
            len(question_tokens & _table_tokens(item[1])),
            -item[0],
        ),
        reverse=True,
    )
    return [label for _, label in ranked_labels[:max_tables_listed]], set()


def review_and_select_from_toc(
    state: AgentState,
    llm: BaseChatModel,
    markdown_store: MarkdownArticleStore,
    *,
    table_store: TableArtifactStore | None = None,
    max_tables_listed: int = 12,
) -> AgentState:
    """Judge each candidate article and select its sections in one structured call.

    The model sees each candidate's title, table of contents, and table labels —
    never a single snippet — so it judges the *article* (is this the right source
    and do its sections hold the facts) rather than whether one arbitrary chunk
    answers the question. This avoids rejecting a correct article because its
    top-ranked chunk happened to be "See also" or the lead infobox.

    Output reuses ``ArticleReview``: ``relevant_sections`` are the section titles
    to read, ``relevant_table_ids`` are immutable normalized artifacts, and
    ``needs_table_reader`` flags computation-oriented table work. The result is
    repaired, never raised: an omitted review defaults to kept, and if the model
    rejects every candidate the best-ranked one is kept so selection is never
    empty (which would starve graph expansion).
    """

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")

    candidates = state.get("article_candidates", [])
    if not candidates:
        return article_review_update(ArticleReviewBatch())

    blocks = []
    section_names_by_source: dict[str, set[str]] = {}
    offered_table_ids_by_source: dict[str, set[str]] = {}
    for candidate in candidates:
        section_titles, table_labels = _article_toc(
            markdown_store, candidate.source_article
        )
        section_names_by_source[candidate.source_article] = set(section_titles)
        table_labels, offered_table_ids = _table_labels_for_review(
            source_article=candidate.source_article,
            question=question,
            sidecar_labels=table_labels,
            table_store=table_store,
            max_tables_listed=max_tables_listed,
        )
        offered_table_ids_by_source[candidate.source_article] = offered_table_ids
        toc = ", ".join(section_titles) if section_titles else "(no section list available)"
        tables = (
            "; ".join(table_labels)
            if table_labels
            else "(no tables listed)"
        )
        blocks.append(
            f"Source article: {candidate.source_article}\n"
            f"Table of contents: {toc}\n"
            f"Tables: {tables}"
        )

    structured_reviewer = llm.with_structured_output(
        ArticleReviewBatch,
        method="function_calling",
    )
    result = structured_reviewer.invoke(
        [
            SystemMessage(content=TOC_REVIEW_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Question:\n{question}\n\n"
                    f"Candidate articles:\n" + "\n\n".join(blocks)
                )
            ),
        ]
    )
    batch = (
        result
        if isinstance(result, ArticleReviewBatch)
        else ArticleReviewBatch.model_validate(result)
    )

    # Reconcile to exactly the candidate set (repair, never raise): use the model's
    # review when present, default an omitted one to kept.
    by_source = {review.source_article: review for review in batch.reviews}
    reviews: list[ArticleReview] = []
    for candidate in candidates:
        review = by_source.get(candidate.source_article)
        if review is None:
            review = ArticleReview(
                source_article=candidate.source_article,
                relevant=True,
                reason="(no explicit review returned; kept)",
            )
        valid_sections = section_names_by_source[candidate.source_article]
        offered_table_ids = offered_table_ids_by_source[candidate.source_article]
        # Preserve an explicit but invalid ID so the loader returns no table
        # instead of falling back to a different semantic match.
        selected_ids = list(review.relevant_table_ids)
        # Accept an artifact ID copied as part of a label, but never allow an
        # invented ID to select a different table by semantic fallback.
        for label in review.relevant_table_names:
            selected_ids.extend(
                table_id
                for table_id in offered_table_ids
                if table_id in label
            )
        review = review.model_copy(
            update={
                "relevant_sections": [
                    section
                    for section in review.relevant_sections
                    if section in valid_sections
                ],
                "relevant_table_ids": list(dict.fromkeys(selected_ids)),
            }
        )
        reviews.append(review)

    # Never reject everything — an empty selection guarantees failure and starves
    # graph expansion, which seeds from the selected articles.
    if not any(review.relevant for review in reviews):
        best_article = min(candidates, key=lambda c: c.rank).source_article
        for review in reviews:
            if review.source_article == best_article:
                review.relevant = True
                review.reason = "(kept as best-ranked candidate; review rejected all)"
                break

    return article_review_update(ArticleReviewBatch(reviews=reviews))


def load_selected_sections(
    state: AgentState,
    retriever: VectorRetriever,
    *,
    hits_per_section: int = 1,
    fallback_sections: int = 2,
) -> AgentState:
    """Load the TOC-selected sections of each kept article into evidence.

    Retrieves each requested section by name inside its article (so the section
    that holds the facts is fetched, not the top-ranked prose chunk). When a kept
    article names no sections, falls back to a question-driven search inside it.
    Table flags from the review are carried into evidence metadata for Phase 2.
    """

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")
    if hits_per_section < 1 or fallback_sections < 1:
        raise ValueError("hits_per_section and fallback_sections must be >= 1.")

    reviews = state.get("article_reviews", [])
    evidence_by_id = {
        item.evidence_id: item for item in state.get("evidence", [])
    }

    for review in reviews:
        if not review.relevant:
            continue
        section_names = [
            name.strip()
            for name in (review.relevant_sections or [])
            if name and name.strip()
        ]
        if section_names:
            plan = [
                (name, name, hits_per_section, "toc_selected_section")
                for name in section_names
            ]
        else:
            plan = [(question, None, fallback_sections, "toc_fallback_sections")]

        for query, requested_section, k, stage in plan:
            if requested_section is not None:
                section_hits = retriever.getArticleSectionTopK(
                    question,
                    review.source_article,
                    requested_section,
                    k=k,
                )
                retrieval_query = question
            else:
                section_hits = retriever.getArticleSectionsTopK(
                    query, review.source_article, k=k
                )
                retrieval_query = query
            for rank, (document, distance) in enumerate(section_hits, start=1):
                metadata = document.metadata
                evidence_id = str(
                    metadata.get("source")
                    or f"{review.source_article}#toc-{requested_section or 'q'}-{rank}"
                )
                if evidence_id in evidence_by_id:
                    continue
                section_title, section_path = _section_identity(metadata)
                evidence_by_id[evidence_id] = EvidenceItem(
                    evidence_id=evidence_id,
                    source_article=review.source_article,
                    content=document.page_content,
                    title=section_title or None,
                    section_path=section_path,
                    retrieval_query=retrieval_query,
                    retriever="vector",
                    rank=rank,
                    raw_score=float(distance),
                    score_semantics="lower_is_better",
                    metadata={
                        "retrieval_stage": stage,
                        "requested_section": requested_section,
                        "needs_table_reader": bool(review.needs_table_reader),
                        "flagged_tables": list(review.relevant_table_names or []),
                        "flagged_table_ids": list(review.relevant_table_ids or []),
                    },
                )

    return {"evidence": list(evidence_by_id.values())}


def _clean_cell(value: object) -> str:
    """Drop soft hyphens and normalize a table cell to plain text."""

    return str(value).replace("­", "").strip()


def _rank_catalog_entries(
    review: ArticleReview,
    catalog: list[TableCatalogEntry],
    question: str,
    *,
    max_tables: int,
) -> list[TableCatalogEntry]:
    """Rank an article's stored tables by relevance to the question.

    Scores each catalog entry on how well its caption, section, columns, and
    legend meanings overlap the question (and, double-weighted, the table names
    the review called out). Keeps the best ``max_tables``; if nothing overlaps,
    falls back to the single largest table (the article was flagged as needing
    one). Ranking the aligned catalog avoids the fragile sidecar "Table N"
    index mapping.
    """

    by_artifact_id = {entry.artifact_id: entry for entry in catalog}
    by_table_id = {entry.table_id.casefold(): entry for entry in catalog}

    if review.relevant_table_ids:
        # Stable IDs are authoritative. Invalid IDs select nothing; silently
        # replacing one with a semantically similar table is worse than missing
        # evidence because it can support a false answer.
        return [
            by_artifact_id[artifact_id]
            for artifact_id in dict.fromkeys(review.relevant_table_ids)
            if artifact_id in by_artifact_id
        ]

    exact_entries: list[TableCatalogEntry] = []
    for selection in review.relevant_table_names or []:
        normalized = selection.strip().casefold()
        match = by_artifact_id.get(selection.strip()) or by_table_id.get(normalized)
        if match is None:
            matching = [
                entry
                for entry in catalog
                if normalized
                in {
                    _table_catalog_label(entry).casefold(),
                    str(entry.caption or "").strip().casefold(),
                    " > ".join(entry.section_path).casefold(),
                }
            ]
            if len(matching) == 1:
                match = matching[0]
        if match is not None and match.artifact_id not in {
            entry.artifact_id for entry in exact_entries
        }:
            exact_entries.append(match)
    if exact_entries:
        # Explicit multi-table selections are all honored. ``max_rows`` in the
        # renderer remains the context budget for each selected artifact.
        return exact_entries

    tokens = _table_tokens(question)
    name_tokens: set[str] = set()
    for label in review.relevant_table_names or []:
        name_tokens |= _table_tokens(str(label))

    def score(entry) -> int:
        hay = " ".join(
            [
                entry.caption or "",
                " ".join(entry.section_path or []),
                " ".join(entry.columns or []),
                " ".join(entry.legend_meanings or []),
            ]
        )
        hay_tokens = _table_tokens(hay)
        return len(tokens & hay_tokens) + 2 * len(
            name_tokens & hay_tokens
        )

    ranked = sorted(catalog, key=lambda e: (score(e), e.row_count), reverse=True)
    chosen = [e for e in ranked if score(e) > 0][:max_tables]
    return chosen or ranked[:1]


def _render_normalized_table_json(
    entry: TableCatalogEntry,
    table: NormalizedTable,
    *,
    max_rows: int,
    max_chars: int = 8000,
) -> str:
    """Render aligned rows plus the rich semantics needed to interpret them.

    ``max_chars`` bounds the rendered evidence so a huge ranked-list table cannot
    overflow the model's context window; the deterministic executor still reads
    the full artifact, so trimming the evidence rows is safe.
    """

    rows: list[dict[str, object]] = []
    for row_index, row in enumerate(table.rows[:max_rows]):
        semantic_signals: dict[str, dict[str, object]] = {}
        rich_row = (
            table.row_cells[row_index]
            if row_index < len(table.row_cells)
            else {}
        )
        for column, cell in rich_row.items():
            signals: dict[str, object] = {
                "source_cell": (
                    f"{table.table_id}:r{cell.origin_row + 1}:"
                    f"c{cell.origin_column + 1}"
                ),
                "display_text": cell.display_text,
                "is_bold": cell.is_bold,
                "is_italic": cell.is_italic,
                "bold_text": cell.bold_text,
                "italic_text": cell.italic_text,
                "annotations": [
                    annotation.model_dump(mode="json")
                    for annotation in cell.annotations
                ],
                "background_color": cell.background_color,
                "sort_value": cell.sort_value,
                "legend_matches": cell.legend_matches,
            }
            has_meaningful_signal = (
                cell.display_text != cell.text
                or cell.is_bold
                or cell.is_italic
                or bool(cell.bold_text)
                or bool(cell.italic_text)
                or bool(cell.annotations)
                or bool(cell.background_color)
                or bool(cell.sort_value)
                or bool(cell.legend_matches)
            )
            if has_meaningful_signal:
                semantic_signals[column] = signals
        rows.append(
            {
                "row_number": row_index + 1,
                "values": {
                    key: _clean_cell(value)
                    for key, value in row.items()
                },
                "semantic_signals": semantic_signals,
            }
        )
    header = (
        "Structured table (JSON rows, one object per row — read values directly "
        "from these rows; do not rely on prior knowledge).\n"
    )

    def _payload(row_limit: int) -> str:
        return json.dumps(
            {
                "artifact_id": entry.artifact_id,
                "table_id": entry.table_id,
                "caption": _clean_cell(entry.caption or "") or None,
                "section": " > ".join(entry.section_path or []) or None,
                "columns": [_clean_cell(c) for c in table.columns],
                "legends": [legend.model_dump(mode="json") for legend in table.legends],
                "rows": rows[:row_limit],
            },
            ensure_ascii=False,
        )

    shown = len(rows)
    body = _payload(shown)
    while shown > 1 and len(header) + len(body) > max_chars:
        shown = max(1, int(shown * max_chars / (len(header) + len(body))) - 1)
        body = _payload(shown)

    text = header + body
    total = len(table.rows)
    if shown < total:
        text += (
            f"\n(NOTE: showing {shown} of {total} rows to fit the context budget; "
            "the deterministic table executor reads the full table.)"
        )
    return text


def load_selected_tables(
    state: AgentState,
    table_store: TableArtifactStore,
    *,
    max_tables_per_article: int = 1,
    max_rows: int = 300,
    max_total_rows_per_article: int = 600,
) -> AgentState:
    """Attach flagged articles' rowspan-expanded tables as structured-JSON evidence.

    Reads from the NormalizedTable artifact store (rowspan/colspan expanded,
    winner markers and legends retained), not the raw sidecar whose rows misalign
    on merged award tables. For each kept article the TOC review flagged, load all
    explicitly selected artifacts. ``max_tables_per_article`` limits only the
    semantic fallback used when the review supplied no resolvable artifact ID.
    ``max_rows`` and ``max_total_rows_per_article`` divide a bounded row budget
    across every selected artifact. The deterministic executor computes over
    these same aligned rows.
    """

    reviews = state.get("article_reviews", [])
    evidence_by_id = {item.evidence_id: item for item in state.get("evidence", [])}
    question = state.get("question", "").strip()
    if (
        max_tables_per_article < 1
        or max_rows < 1
        or max_total_rows_per_article < 1
    ):
        raise ValueError(
            "max_tables_per_article, max_rows, and "
            "max_total_rows_per_article must be at least 1."
        )

    for review in reviews:
        if not review.relevant:
            continue
        if not (
            review.needs_table_reader
            or review.relevant_table_ids
            or review.relevant_table_names
        ):
            continue
        try:
            article = resolve_source_article(review.source_article, table_store)
        except (KeyError, ValueError):
            continue
        catalog = table_store.list_tables(article)
        if not catalog:
            continue
        selected_entries = _rank_catalog_entries(
            review, catalog, question, max_tables=max_tables_per_article
        )
        rows_per_table = max(
            1,
            min(
                max_rows,
                max_total_rows_per_article // max(len(selected_entries), 1),
            ),
        )
        for table_rank, entry in enumerate(selected_entries, start=1):
            evidence_id = f"{entry.source_article}#{entry.table_id}"
            if evidence_id in evidence_by_id:
                continue
            try:
                table = table_store.load_artifact(entry.artifact_id)
            except (OSError, ValueError, KeyError):
                continue
            evidence_by_id[evidence_id] = EvidenceItem(
                evidence_id=evidence_id,
                source_article=entry.source_article,
                content=_render_normalized_table_json(
                    entry,
                    table,
                    max_rows=rows_per_table,
                ),
                evidence_type="table",
                title=_clean_cell(entry.caption or "") or entry.table_id,
                section_path=list(entry.section_path or []),
                retrieval_query=question,
                retriever="table",
                rank=table_rank,
                raw_score=0.0,
                score_semantics="rank_only",
                table_id=entry.artifact_id,
                metadata={
                    "retrieval_stage": "toc_selected_table",
                    "table_id": entry.table_id,
                    "n_rows": entry.row_count,
                    "rows_rendered": min(entry.row_count, rows_per_table),
                    "needs_table_reader": bool(review.needs_table_reader),
                },
            )

    return {"evidence": list(evidence_by_id.values())}


def retrieve_selected_article_sections(
    state: AgentState,
    retriever: VectorRetriever,
    *,
    sections_per_article: int = 3,
) -> AgentState:
    """Retrieve additional focused evidence during a follow-up retrieval branch."""

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")
    if sections_per_article < 1:
        raise ValueError("sections_per_article must be at least 1.")

    selected_articles = state.get("selected_articles", [])
    existing_evidence = state.get("evidence", [])
    evidence_by_id = {
        item.evidence_id: item
        for item in existing_evidence
    }

    for source_article in selected_articles:
        section_hits = retriever.getArticleSectionsTopK(
            question,
            source_article,
            k=sections_per_article,
        )
        for rank, (document, score) in enumerate(section_hits, start=1):
            metadata = document.metadata
            evidence_id = str(
                metadata.get("source")
                or f"{source_article}#retrieved-section-{rank}"
            )
            section_title, section_path = _section_identity(metadata)

            evidence_by_id[evidence_id] = EvidenceItem(
                evidence_id=evidence_id,
                source_article=source_article,
                content=document.page_content,
                title=section_title or None,
                section_path=section_path,
                retrieval_query=question,
                retriever="vector",
                rank=rank,
                raw_score=score,
                score_semantics="lower_is_better",
                metadata={"retrieval_stage": "selected_article_sections"},
            )

    return {"evidence": list(evidence_by_id.values())}


def retrieve_broadened_article_sections(
    state: AgentState,
    retriever: VectorRetriever,
    *,
    broaden_k: int = 8,
) -> AgentState:
    """Widen context on the already-selected articles for synthesis questions.

    5.1 restricts initial evidence to the TOC-selected sections — a bet that bought
    perfect recall and table precision, but starves questions whose answer is spread
    across an article (people-connection, process-explanation), which 2.1-4.1
    answered from full-article context. This escalation pulls the top ``broaden_k``
    sections of each kept article by relevance to the question, adding the breadth
    those questions need. It is additive (never drops existing evidence, and dedups
    by section id, so it only contributes sections beyond the ones already selected)
    and it touches neither the graph route (neighbor articles) nor the table route.
    """

    if broaden_k < 1:
        raise ValueError("broaden_k must be at least 1.")

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")

    seeds = list(dict.fromkeys(state.get("selected_articles", [])))
    evidence_by_id = {
        item.evidence_id: item for item in state.get("evidence", [])
    }
    for source_article in seeds:
        section_hits = retriever.getArticleSectionsTopK(
            question, source_article, k=broaden_k
        )
        for rank, (document, distance) in enumerate(section_hits, start=1):
            metadata = document.metadata
            evidence_id = str(
                metadata.get("source")
                or f"{source_article}#broaden-{rank}"
            )
            if evidence_id in evidence_by_id:
                continue
            section_title, section_path = _section_identity(metadata)
            evidence_by_id[evidence_id] = EvidenceItem(
                evidence_id=evidence_id,
                source_article=source_article,
                content=document.page_content,
                title=section_title or None,
                section_path=section_path,
                retrieval_query=question,
                retriever="vector",
                rank=rank,
                raw_score=float(distance),
                score_semantics="lower_is_better",
                metadata={"retrieval_stage": "broadened_article_sections"},
            )

    return {
        "evidence": list(evidence_by_id.values()),
        "retrieval_attempts": retrieval_attempt_count(state) + 1,
    }


def retrieve_whole_article_evidence(
    state: AgentState,
    retriever: VectorRetriever,
    *,
    load_text: ArticleTextLoader,
    broaden_k: int = 8,
) -> AgentState:
    """Widen context with whole articles: the Checkpoint 6.1 replacement for broadening.

    When no kept article needs a table (the per-question rule of
    ``answer_context``), each kept article's evidence is replaced by its whole text,
    so the next assessment and the answer read the complete articles. A question with
    a table keeps the 5.1 behavior: the top ``broaden_k`` sections of each selected
    article are added.
    """

    whole = articles_to_send_whole(state, "whole_per_question")
    if not whole:
        return retrieve_broadened_article_sections(state, retriever, broaden_k=broaden_k)
    return {
        "evidence": replace_with_whole_articles(list(state.get("evidence", [])), whole, load_text),
        "retrieval_attempts": retrieval_attempt_count(state) + 1,
    }


def retrieve_graph_seeded_evidence(
    state: AgentState,
    retriever: VectorRetriever,
    graph: WikiGraph,
    *,
    graph_params: GraphParams | None = None,
    sections_per_neighbor: int = 2,
    max_graph_sections: int = 6,
) -> AgentState:
    """Expand selected VS articles, then retrieve only relevant neighbor sections.

    The graph chooses related article names. It never supplies answer context itself.
    For every related article, the section-aware vector retriever selects the chunks
    relevant to the assessor's missing-fact query. All neighbor-section candidates
    are then ranked by match distance and only the ``max_graph_sections`` best
    become ``EvidenceItem`` objects, so a semantically adjacent but off-topic
    neighbor cannot inject distractor chunks just for being a graph neighbor.
    """

    if sections_per_neighbor < 1:
        raise ValueError("sections_per_neighbor must be at least 1.")
    if max_graph_sections < 1:
        raise ValueError("max_graph_sections must be at least 1.")

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")

    seeds = list(dict.fromkeys(state.get("selected_articles", [])))
    existing_evidence = state.get("evidence", [])
    evidence_by_id = {item.evidence_id: item for item in existing_evidence}
    next_attempt = retrieval_attempt_count(state) + 1
    if not seeds:
        return {
            "evidence": list(evidence_by_id.values()),
            "retrieval_attempts": next_attempt,
        }

    assessment = state.get("assessment")
    retrieval_queries = (
        [request.query.strip() for request in assessment.retrieval_requests]
        if assessment is not None
        else []
    )
    retrieval_queries = list(
        dict.fromkeys(query for query in retrieval_queries if query)
    ) or [question]

    params = graph_params or GraphParams()
    neighbors = graph.expand(seeds, params)

    # Gather every candidate neighbor section first, then keep only the globally
    # best-matching ones. Adding the top-k sections of *every* neighbor lets a
    # semantically adjacent but wrong article (e.g. a sibling award page) inject
    # distractor chunks; ranking all candidates by match distance and capping the
    # total keeps the on-topic neighbors and drops that tail.
    candidates: list[dict] = []
    for neighbor_rank, (article, graph_score, reasons) in enumerate(
        neighbors,
        start=1,
    ):
        for retrieval_query in retrieval_queries:
            section_hits = retriever.getArticleSectionsTopK(
                retrieval_query,
                article,
                k=sections_per_neighbor,
            )
            for section_rank, (document, distance) in enumerate(
                section_hits,
                start=1,
            ):
                candidates.append(
                    {
                        "distance": float(distance),
                        "neighbor_rank": neighbor_rank,
                        "section_rank": section_rank,
                        "article": article,
                        "graph_score": graph_score,
                        "reasons": reasons,
                        "document": document,
                        "retrieval_query": retrieval_query,
                    }
                )

    # Lower Chroma distance is a closer match, so the best candidates sort first.
    candidates.sort(key=lambda item: item["distance"])

    added = 0
    for candidate in candidates:
        if added >= max_graph_sections:
            break
        document = candidate["document"]
        article = candidate["article"]
        metadata = document.metadata
        evidence_id = str(
            metadata.get("source")
            or f"{article}#graph-section-{candidate['section_rank']}"
        )
        if evidence_id in evidence_by_id:
            continue
        section_title, section_path = _section_identity(metadata)
        evidence_by_id[evidence_id] = EvidenceItem(
            evidence_id=evidence_id,
            source_article=article,
            content=document.page_content,
            evidence_type="graph",
            title=section_title or None,
            section_path=section_path,
            retrieval_query=candidate["retrieval_query"],
            retriever="graph",
            rank=candidate["section_rank"],
            raw_score=candidate["distance"],
            score_semantics="lower_is_better",
            metadata={
                "retrieval_stage": "graph_seeded_sections",
                "seed_articles": seeds,
                "graph_neighbor_rank": candidate["neighbor_rank"],
                "graph_score": candidate["graph_score"],
                "discovery_reasons": candidate["reasons"],
            },
        )
        added += 1

    return {
        "evidence": list(evidence_by_id.values()),
        "retrieval_attempts": next_attempt,
    }


def _section_identity(metadata: dict) -> tuple[str, list[str]]:
    """Normalize section title/path metadata emitted by Chroma."""

    raw_section_path = metadata.get("section_path", "")
    if isinstance(raw_section_path, (list, tuple)):
        section_path = [
            str(part).strip()
            for part in raw_section_path
            if str(part).strip()
        ]
    else:
        section_path = [
            part.strip()
            for part in str(raw_section_path).split(">")
            if part.strip()
        ]
    section_title = str(
        metadata.get("section_title")
        or (section_path[-1] if section_path else "")
    ).strip()
    return section_title, section_path


def assess_evidence(
    state: AgentState,
    llm: BaseChatModel,
    *,
    allow_table_requests: bool = True,
    breadth_nudge: bool = False,
) -> AgentState:
    """Assess completeness and produce requests for the graph's next branch."""

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")

    reviews = state.get("article_reviews", [])
    evidence = state.get("evidence", [])

    review_context = "\n\n".join(
        (
            f"Source article: {review.source_article}\n"
            f"Relevant: {review.relevant}\n"
            f"Reason: {review.reason}\n"
            f"Needs table reader: {review.needs_table_reader}\n"
            f"Relevant sections: {', '.join(review.relevant_sections) or '(none)'}\n"
            f"Relevant tables: {', '.join(review.relevant_table_names) or '(none)'}\n"
            f"Relevant table artifact IDs: "
            f"{', '.join(review.relevant_table_ids) or '(none)'}"
        )
        for review in reviews
    ) or "(no article reviews available)"

    evidence_context = "\n\n".join(
        (
            f"Evidence ID: {item.evidence_id}\n"
            f"Source article: {item.source_article}\n"
            f"Section: {' > '.join(item.section_path) or item.title or '(unknown)'}\n"
            f"Evidence type: {item.evidence_type}\n"
            f"Retrieval stage: {item.metadata.get('retrieval_stage', 'unknown')}\n"
            f"Content:\n{item.content}"
        )
        for item in evidence
    ) or "(no evidence available)"

    structured_assessor = llm.with_structured_output(
        EvidenceAssessment,
        method="function_calling",
    )
    benchmark_constraint = ""
    if not allow_table_requests:
        benchmark_constraint = (
            "\n\nRetrieval-only benchmark constraint:\n"
            "- The table-reader tool is unavailable in this experiment.\n"
            "- Always leave table_requests empty.\n"
            "- If evidence is missing even when it may appear in a table, create a "
            "focused retrieval_request for the missing fact instead."
        )

    messages = [
        SystemMessage(
            content=EVIDENCE_ASSESSMENT_SYSTEM_PROMPT + benchmark_constraint
        ),
        HumanMessage(
            content=(
                f"Question:\n{question}\n\n"
                f"Article reviews:\n{review_context}\n\n"
                f"Retrieved evidence:\n{evidence_context}"
            )
        ),
    ]
    # Malformed structured output (often a bad table_request) must never drop the
    # question. Retry once with the schema error as a correction, then fall back to
    # a safe not-ready assessment that keeps the loop going.
    try:
        result = structured_assessor.invoke(messages)
    except Exception as parse_error:  # noqa: BLE001 - any parse/validation failure
        correction = SystemMessage(
            content=(
                "Your previous response failed schema validation:\n"
                f"{parse_error}\n"
                "Return a valid EvidenceAssessment. Keep each table_request minimal — "
                "only missing_fact, source_article, table_id, and a valid operation "
                "(lookup/filter/aggregate/compare/sort/timeline); never put numbers "
                "in row_filters."
            )
        )
        try:
            result = structured_assessor.invoke([*messages, correction])
        except Exception:  # noqa: BLE001
            result = None

    if result is None:
        assessment = EvidenceAssessment(
            ready_to_answer=False,
            explanation="Assessment output could not be parsed; continuing retrieval.",
        )
    else:
        assessment = (
            result
            if isinstance(result, EvidenceAssessment)
            else EvidenceAssessment.model_validate(result)
        )

    # Repair imperfect structured output instead of dropping the question.
    # gpt-5.4-mini occasionally returns self-contradictory or incomplete
    # assessments; a hard raise here silently removes that question from the
    # benchmark, so coerce to a consistent, actionable state and keep going.

    # Retrieval-only benchmark: the table reader is disabled, so ignore any
    # table requests the model emitted rather than failing the run.
    if not allow_table_requests and assessment.table_requests:
        assessment.table_requests = []

    # Trust the gaps over the flag: a "ready" verdict that still lists missing
    # requirements, open requests, or unresolved conflicts is not actually
    # ready, so keep the retrieval loop running.
    if assessment.ready_to_answer and (
        assessment.missing_requirements
        or assessment.retrieval_requests
        or assessment.table_requests
        or assessment.unresolved_conflicts
    ):
        assessment.ready_to_answer = False

    # Single table gateway: every relevant selected table must pass through the
    # deterministic executor before we answer, rather than letting the model read
    # rows off the page. The planner classifies each request (lookup vs filter/
    # aggregate/...) via operation="auto". Extraction is additive, so prose and
    # quotation evidence is preserved untouched; a table only adds a deterministic
    # result. This stands down once a table_computation result already exists so
    # the loop cannot spin on it.
    if allow_table_requests:
        needs_extraction = any(
            review.relevant and review.relevant_table_ids for review in reviews
        )
        already_computed = any(
            item.metadata.get("retrieval_stage") == "table_computation"
            for item in evidence
        )
        if needs_extraction and not already_computed:
            assessment.ready_to_answer = False
            if not assessment.table_requests:
                assessment.table_requests = [
                    TableRequest(
                        missing_fact=question,
                        source_article=review.source_article,
                        table_id=table_id,
                        operation="auto",
                    )
                    for review in reviews
                    if review.relevant and review.relevant_table_ids
                    for table_id in review.relevant_table_ids
                ]

    # Breadth nudge: a non-table question answered straight from its initial single
    # section is often starved -- the assessor calls "ready" on one section and
    # answers partially (validation Step 8). Deny that first-pass "ready" so the
    # question takes one escalation (article_broaden leads the repeated sequence) and
    # gets the fuller article context 2.1-4.1 had. Fires only at the initial pass
    # (attempts <= 1): after one escalation the assessor's verdict is honored, so the
    # loop stays bounded and a question that truly needs only its one section costs a
    # single extra round, not many. Table questions are handled by the gateway above.
    is_table_question = any(
        review.relevant and review.relevant_table_ids for review in reviews
    )
    if (
        breadth_nudge
        and not is_table_question
        and assessment.ready_to_answer
        and retrieval_attempt_count(state) <= 1
        and state.get("selected_articles")
    ):
        assessment.ready_to_answer = False

    # A not-ready assessment with no actionable request would stall the loop.
    # Fall back to re-querying the original question so retrieval can progress.
    if not assessment.ready_to_answer and not (
        assessment.retrieval_requests or assessment.table_requests
    ):
        assessment.retrieval_requests = [
            RetrievalRequest(
                missing_fact=(
                    "; ".join(assessment.missing_requirements)
                    or "Outstanding information required to answer the question."
                ),
                query=question,
            )
        ]

    return {
        "assessment": assessment,
        "assessment_history": [
            *state.get("assessment_history", []),
            assessment,
        ],
    }


def retrieve_multistep_evidence(
    state: AgentState,
    retriever: MultiStepRetriever,
    *,
    hits_per_request: int = 6,
) -> AgentState:
    """Run targeted query decomposition and retain its section chunks as evidence."""

    if hits_per_request < 1:
        raise ValueError("hits_per_request must be at least 1.")

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")

    assessment = state.get("assessment")
    retrieval_queries = (
        [request.query.strip() for request in assessment.retrieval_requests]
        if assessment is not None
        else []
    )
    retrieval_queries = list(
        dict.fromkeys(query for query in retrieval_queries if query)
    ) or [question]

    evidence_by_id = {
        item.evidence_id: item
        for item in state.get("evidence", [])
    }
    for retrieval_query in retrieval_queries:
        hits, reasoning = retriever.retrieve_with_reasoning(
            retrieval_query,
            k=hits_per_request,
        )
        for rank, (doc_id, content, score) in enumerate(hits, start=1):
            if doc_id in evidence_by_id:
                continue
            source_article = doc_id.split("#", 1)[0]
            evidence_by_id[doc_id] = EvidenceItem(
                evidence_id=doc_id,
                source_article=source_article,
                content=content,
                retrieval_query=retrieval_query,
                retriever="vector",
                rank=rank,
                raw_score=float(score),
                score_semantics="higher_is_better",
                metadata={
                    "retrieval_stage": "targeted_multistep_sections",
                    "reasoning_instructions": reasoning,
                },
            )

    return {
        "evidence": list(evidence_by_id.values()),
        "retrieval_attempts": retrieval_attempt_count(state) + 1,
    }


def route_after_evidence_assessment(state: AgentState) -> EvidenceRoute:
    """Choose the next graph edge from the structured evidence assessment."""

    assessment = state.get("assessment")
    if assessment is None:
        raise ValueError("Agent state does not contain an evidence assessment.")
    if assessment.ready_to_answer:
        return "ready_to_answer"
    if assessment.table_requests:
        return "need_table_reader"
    return "need_more_evidence"
