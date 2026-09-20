from __future__ import annotations

from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from wikipedia_retrieval_engine.retrievers.vector import VectorRetriever
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    ArticleReviewBatch,
    EvidenceAssessment,
    EvidenceItem,
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
- Use table operations such as lookup, filter, aggregate, compare, sort, or
  timeline to describe the required table work.
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
) -> AgentState:
    """Find the initial article candidates for a question."""

    question = state.get("question", "").strip()
    if not question:
        raise ValueError("Agent state must contain a non-empty question.")

    article_candidates = retriever.getArticlesTopK(question, k=3)

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


def assess_evidence(
    state: AgentState,
    llm: BaseChatModel,
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
            f"Relevant tables: {', '.join(review.relevant_table_names) or '(none)'}"
        )
        for review in reviews
    ) or "(no article reviews available)"

    evidence_context = "\n\n".join(
        (
            f"Evidence ID: {item.evidence_id}\n"
            f"Source article: {item.source_article}\n"
            f"Section: {' > '.join(item.section_path) or item.title or '(unknown)'}\n"
            f"Content:\n{item.content}"
        )
        for item in evidence
    ) or "(no evidence available)"

    structured_assessor = llm.with_structured_output(
        EvidenceAssessment,
        method="function_calling",
    )
    result = structured_assessor.invoke(
        [
            SystemMessage(content=EVIDENCE_ASSESSMENT_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Question:\n{question}\n\n"
                    f"Article reviews:\n{review_context}\n\n"
                    f"Retrieved evidence:\n{evidence_context}"
                )
            ),
        ]
    )
    assessment = (
        result
        if isinstance(result, EvidenceAssessment)
        else EvidenceAssessment.model_validate(result)
    )

    if assessment.ready_to_answer and (
        assessment.missing_requirements
        or assessment.retrieval_requests
        or assessment.table_requests
        or assessment.unresolved_conflicts
    ):
        raise ValueError(
            "A ready-to-answer assessment cannot contain missing requirements, "
            "requests, or unresolved conflicts."
        )
    if not assessment.ready_to_answer and not (
        assessment.retrieval_requests or assessment.table_requests
    ):
        raise ValueError(
            "An incomplete assessment must include a retrieval or table request."
        )

    return {"assessment": assessment}


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
