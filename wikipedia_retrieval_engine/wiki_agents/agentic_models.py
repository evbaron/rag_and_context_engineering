from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """One evidence unit carried through retrieval, assessment, and answering.

    ``raw_score`` is deliberately paired with ``score_semantics`` because BM25
    scores, Chroma distances, and fused ranks cannot safely be compared as though
    they were all higher-is-better similarities.
    """

    evidence_id: str = Field(min_length=1)
    source_article: str = Field(min_length=1)
    content: str = Field(min_length=1)
    evidence_type: Literal["text", "table", "infobox", "graph"] = "text"

    title: str | None = None
    section_path: list[str] = Field(default_factory=list)

    retrieval_query: str | None = None
    retriever: Literal["vector", "bm25", "hybrid", "graph", "table"] | None = None
    rank: int | None = Field(default=None, ge=1)
    raw_score: float | None = None
    score_semantics: Literal[
        "higher_is_better",
        "lower_is_better",
        "rank_only",
        "unknown",
    ] = "unknown"

    # Populated when the evidence was derived from a normalized table.
    table_id: str | None = None
    source_cells: list[str] = Field(default_factory=list)

    # Backend-specific details that should not become top-level state fields.
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalRequest(BaseModel):
    missing_fact: str
    query: str
    target_articles: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    preferred_retriever: Literal[
        "vector", "bm25", "hybrid", "graph"
    ] = "hybrid"


class AnswerClaim(BaseModel):
    claim: str
    evidence_ids: list[str]
    calculation: str | None = None


class DraftAnswer(BaseModel):
    answer: str
    claims: list[AnswerClaim]
    limitations: list[str]


class TableQueryPlan(BaseModel):
    operation: Literal["lookup", "filter", "aggregate", "compare", "sort"]
    selected_columns: list[str]
    filters: dict[str, str]
    group_by: list[str]
    calculation: str | None
    sort_column: str | None
    sort_direction: Literal["ascending", "descending"] | None
    limit: int | None


class TableEvidence(BaseModel):
    request_id: str
    artifact_id: str
    result_rows: list[dict[str, str | int | float]]
    calculation: str | None
    source_cells: list[str]  # e.g. table-002:r17:c3
    sufficient: bool
    warnings: list[str]


class TableRequest(BaseModel):
    missing_fact: str
    source_article: str
    table_id: str | None = None
    expected_caption: str | None = None
    operation: Literal[
        "lookup",
        "filter",
        "aggregate",
        "compare",
        "sort",
        "timeline",
    ]
    columns_needed: list[str] = Field(default_factory=list)
    row_filters: dict[str, str] = Field(default_factory=dict)
    comparison_key: str | None = None


class EvidenceAssessment(BaseModel):
    ready_to_answer: bool
    supported_requirements: list[str]
    missing_requirements: list[str]
    retrieval_requests: list[RetrievalRequest]
    table_requests: list[TableRequest]
    unresolved_conflicts: list[str]
    explanation: str


class EvidenceRequirement(BaseModel):
    requirement_id: str
    description: str
    evidence_ids: list[str]
    satisfied: bool
    reason: str


class AnswerVerification(BaseModel):
    """Auditable result of checking a draft against its cited evidence."""

    supported: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    invalid_evidence_ids: list[str] = Field(default_factory=list)
    calculation_errors: list[str] = Field(default_factory=list)
    explanation: str


class AgentState(TypedDict, total=False):
    # Request
    question: str
    requirements: list[EvidenceRequirement]

    # Retrieval
    active_queries: list[str]
    attempted_queries: list[str]
    evidence: list[EvidenceItem]
    seen_evidence_ids: list[str]

    # Assessment
    assessment: EvidenceAssessment
    route: str

    # Tables
    table_requests: list[TableRequest]
    table_artifacts: list[TableEvidence]

    # Budgets
    retrieval_attempts: int
    table_attempts: int
    answer_repairs: int

    # Output
    draft_answer: DraftAnswer
    verification: AnswerVerification
    final_answer: str
    termination_reason: str
