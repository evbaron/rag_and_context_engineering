"""Answer-context rules: which representation of the evidence the answer model reads.

The 5.1 survivor answers from the accumulated section and table evidence
(rule ``"sections"``). Checkpoint 6.1 tests whether whole articles serve
text-rich questions better, while table questions keep the table path:

    sections            the 5.1 evidence, unchanged
    whole_per_question  if no kept article needs a table, every kept article is
                        sent whole; otherwise the 5.1 evidence, unchanged
    whole_per_article   each kept article that needs no table is sent whole; an
                        article that needs a table keeps its sections and table
                        evidence

"Kept" articles are the ones the TOC review marked relevant; "needs a table"
uses the same flag as the 5.1 harness's ``tables_flagged`` column. The rules work
on a finished ``AgentState``, so they apply equally to a live graph run and to a
state reloaded from a 5.1 log (the Checkpoint 6.1 answer replay).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    ArticleReview,
    EvidenceItem,
)

ContextRule = Literal["sections", "whole_per_question", "whole_per_article"]
CONTEXT_RULES: tuple[ContextRule, ...] = ("sections", "whole_per_question", "whole_per_article")

WHOLE_ARTICLE_STAGE = "whole_article"

# Returns an article's full text, or None when it is not available.
ArticleTextLoader = Callable[[str], str | None]


def needs_table(review: ArticleReview) -> bool:
    """True when the TOC review flagged this article's tables as needed."""

    return bool(review.needs_table_reader or review.relevant_table_ids or review.relevant_table_names)


def kept_reviews(state: AgentState) -> list[ArticleReview]:
    """Reviews of the articles the TOC review kept, in review order."""

    return [review for review in state.get("article_reviews", []) if review.relevant]


def articles_to_send_whole(state: AgentState, rule: ContextRule) -> list[str]:
    """The kept articles whose evidence ``rule`` replaces with the whole article."""

    kept = kept_reviews(state)
    if rule == "sections":
        return []
    if rule == "whole_per_question":
        if any(needs_table(review) for review in kept):
            return []
        return [review.source_article for review in kept]
    if rule == "whole_per_article":
        return [review.source_article for review in kept if not needs_table(review)]
    raise ValueError(f"Unknown context rule: {rule!r}")


def whole_article_item(source_article: str, text: str) -> EvidenceItem:
    """One evidence item carrying a whole article, in the 5.1 evidence format."""

    return EvidenceItem(
        evidence_id=f"{WHOLE_ARTICLE_STAGE}:{source_article}",
        source_article=source_article,
        content=text,
        section_path=["(whole article)"],
        metadata={"retrieval_stage": WHOLE_ARTICLE_STAGE},
    )


def replace_with_whole_articles(
    evidence: list[EvidenceItem],
    articles: list[str],
    load_text: ArticleTextLoader,
) -> list[EvidenceItem]:
    """Swap each listed article's evidence items for one whole-article item.

    - The whole-article item takes the position of that article's first evidence
      item, so articles keep their relative order.
    - Evidence from other articles (for example graph neighbors) is unchanged.
    - A listed article with no evidence items is appended at the end.
    - An article whose text cannot be loaded keeps its evidence items.
    """

    texts: dict[str, str] = {}
    for article in dict.fromkeys(articles):
        text = load_text(article)
        if text and text.strip():
            texts[article] = text

    result: list[EvidenceItem] = []
    placed: set[str] = set()
    for item in evidence:
        article = item.source_article
        if article not in texts:
            result.append(item)
        elif article not in placed:
            result.append(whole_article_item(article, texts[article]))
            placed.add(article)
    result.extend(
        whole_article_item(article, text) for article, text in texts.items() if article not in placed
    )
    return result


def build_answer_evidence(
    state: AgentState,
    rule: ContextRule,
    load_text: ArticleTextLoader,
) -> list[EvidenceItem]:
    """The evidence the answer model receives under ``rule``."""

    evidence = list(state.get("evidence", []))
    whole = articles_to_send_whole(state, rule)
    if not whole:
        return evidence
    return replace_with_whole_articles(evidence, whole, load_text)
