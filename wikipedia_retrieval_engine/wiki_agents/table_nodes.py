"""Deterministic helpers for the Checkpoint 5.1 table-reader branch."""

from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from wikipedia_retrieval_engine.utils.wiki_table_store import (
    TableArtifactStore,
    TableCatalogEntry,
)
from wikipedia_retrieval_engine.utils.wiki_table_parser import NormalizedTable
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    TableCellEvidence,
    TableEvidence,
    TableQueryPlan,
    TableRequest,
)


TABLE_QUERY_PLANNER_SYSTEM_PROMPT = """
You plan one operation over normalized Wikipedia table artifacts.

Rules:
- Choose exactly one artifact_id from the supplied candidates.
- Preserve the requested operation exactly.
- Use only exact column names shown for the chosen artifact.
- selected_columns are the columns whose cells the executor should return.
- filters map an exact column name to a case-insensitive text value that must occur
  in that cell. They identify rows; they do not extract or calculate the answer.
- group_by and sort_column must also use exact column names.
- calculation, when required, must be count, sum, min, max, or average.
- calculation_column identifies the exact numeric column for sum, min, max, or
  average. A count does not require calculation_column.
- Use limit only when the request calls for a bounded number of rows.
- Rich cell signals such as bold_text, annotations, colors, and legend_matches are
  preserved by the artifact and will be interpreted after row selection.
- Do not answer the user's question and do not invent data.
""".strip()


def resolve_source_article(
    source_article: str,
    table_store: TableArtifactStore,
) -> str:
    """Resolve a model-supplied article label to one stored article filename.

    The assessor is instructed to preserve the exact source filename, but this
    small normalization boundary also accepts harmless variations such as spaces
    instead of underscores or an omitted ``.html`` suffix. Ambiguous or unknown
    labels are rejected rather than guessed.
    """

    supplied = Path(source_article.strip()).name
    if table_store.has_article(supplied):
        return supplied

    normalized = _article_key(supplied)
    matches = [
        article
        for article in table_store.list_articles()
        if _article_key(article) == normalized
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise KeyError(f"No table artifact exists for article: {source_article}")
    raise ValueError(
        f"Article label {source_article!r} is ambiguous in the table store: {matches}"
    )


def find_table_candidates(
    request: TableRequest,
    table_store: TableArtifactStore,
    *,
    limit: int = 3,
) -> list[TableCatalogEntry]:
    """Return the best catalog entries for one structured table request.

    Explicit table IDs are treated as authoritative. Otherwise the immutable
    artifact is ranked using catalog metadata and normalized row text. Row text
    is necessary for Wikipedia layout tables that have no caption and only
    generic column names such as ``column_1``.
    """

    if limit < 1:
        raise ValueError("limit must be at least 1.")

    source_article = resolve_source_article(request.source_article, table_store)
    article_tables = table_store.list_tables(source_article)

    if request.table_id:
        matches = [
            entry
            for entry in article_tables
            if entry.table_id == request.table_id
            or entry.artifact_id == request.table_id
        ]
        if not matches:
            raise KeyError(
                f"Table {request.table_id!r} is not present in {source_article}"
            )
        return matches[:limit]

    expected_caption = (request.expected_caption or "").strip().casefold()
    if expected_caption:
        caption_matches = [
            entry
            for entry in article_tables
            if (entry.caption or "").strip().casefold() == expected_caption
            or any(
                section.strip().casefold() == expected_caption
                for section in entry.section_path
            )
        ]
        if caption_matches:
            return caption_matches[:limit]

    query_parts = [
        request.missing_fact,
        request.expected_caption or "",
        *request.columns_needed,
        *request.row_filters.keys(),
        *request.row_filters.values(),
        request.comparison_key or "",
    ]
    query = " ".join(part.strip() for part in query_parts if part.strip())
    query_tokens = _search_tokens(query)
    normalized_by_id = {
        table.table_id: table
        for table in table_store.load_article(source_article)
        if table.table_role != "legend"
    }

    filter_values = [
        " ".join(value.casefold().split())
        for value in request.row_filters.values()
        if value.strip()
    ]
    ranked: list[tuple[int, int, int, int, TableCatalogEntry]] = []
    for position, entry in enumerate(article_tables):
        metadata_text = " ".join(
            [
                entry.caption or "",
                *entry.section_path,
                *entry.columns,
                *entry.legend_meanings,
            ]
        )
        metadata_overlap = len(query_tokens & _search_tokens(metadata_text))

        table = normalized_by_id.get(entry.table_id)
        row_overlap = 0
        filter_matches = 0
        if table is not None:
            row_text = " ".join(
                value
                for row in table.rows
                for value in row.values()
            )
            row_tokens = {
                token
                for token in _search_tokens(row_text)
            }
            row_overlap = len(query_tokens & row_tokens)
            normalized_row_text = " ".join(row_text.casefold().split())
            filter_matches = sum(
                value in normalized_row_text
                for value in filter_values
            )

        # Exact requested values are the strongest signal. Metadata and row text
        # then contribute equally so captionless/layout tables remain eligible.
        score = (filter_matches * 6) + (metadata_overlap * 2) + (row_overlap * 2)
        if score:
            ranked.append(
                (score, filter_matches, metadata_overlap, -position, entry)
            )

    ranked.sort(key=lambda item: item[:4], reverse=True)
    return [entry for _, _, _, _, entry in ranked[:limit]]


def plan_table_query(
    question: str,
    request: TableRequest,
    table_store: TableArtifactStore,
    llm: BaseChatModel,
    *,
    candidate_limit: int = 3,
    sample_rows: int = 3,
) -> TableQueryPlan:
    """Use structured model output to plan—but not execute—one table request."""

    if not question.strip():
        raise ValueError("A non-empty user question is required.")
    if sample_rows < 1:
        raise ValueError("sample_rows must be at least 1.")

    candidates = find_table_candidates(
        request,
        table_store,
        limit=candidate_limit,
    )
    if not candidates:
        raise ValueError(
            "No table candidates matched the request for "
            f"{request.source_article}."
        )

    tables = {
        candidate.artifact_id: table_store.load_artifact(candidate.artifact_id)
        for candidate in candidates
    }
    candidate_context = [
        _table_planner_context(
            candidate,
            tables[candidate.artifact_id],
            request,
            sample_rows=sample_rows,
        )
        for candidate in candidates
    ]

    structured_planner = llm.with_structured_output(
        TableQueryPlan,
        method="function_calling",
    )
    result = structured_planner.invoke(
        [
            SystemMessage(content=TABLE_QUERY_PLANNER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"User question:\n{question.strip()}\n\n"
                    "Table request:\n"
                    f"{request.model_dump_json(indent=2)}\n\n"
                    "Candidate table artifacts:\n"
                    f"{json.dumps(candidate_context, indent=2, ensure_ascii=False)}"
                )
            ),
        ]
    )
    plan = (
        result
        if isinstance(result, TableQueryPlan)
        else TableQueryPlan.model_validate(result)
    )
    _validate_table_query_plan(plan, request, tables)
    return plan


def _validate_table_query_plan(
    plan: TableQueryPlan,
    request: TableRequest,
    candidate_tables: dict[str, NormalizedTable],
) -> None:
    """Reject a plan that escapes the candidates or invents schema fields."""

    table = candidate_tables.get(plan.artifact_id)
    if table is None:
        raise ValueError(
            "Table planner selected an artifact that was not supplied: "
            f"{plan.artifact_id}"
        )
    if plan.operation != request.operation:
        raise ValueError(
            "Table planner changed the requested operation from "
            f"{request.operation!r} to {plan.operation!r}."
        )

    known_columns = set(table.columns)
    referenced_columns = {
        *plan.selected_columns,
        *plan.filters.keys(),
        *plan.group_by,
    }
    if plan.sort_column:
        referenced_columns.add(plan.sort_column)
    if plan.calculation_column:
        referenced_columns.add(plan.calculation_column)
    unknown_columns = sorted(referenced_columns - known_columns)
    if unknown_columns:
        raise ValueError(
            f"Table planner invented columns for {plan.artifact_id}: "
            f"{unknown_columns}. Available columns: {table.columns}."
        )
    if not plan.selected_columns:
        raise ValueError("Table query plan must select at least one column.")
    if plan.operation in {"sort", "timeline"} and not plan.sort_column:
        raise ValueError(
            f"A {plan.operation!r} table plan requires sort_column."
        )
    if plan.operation == "aggregate" and not plan.calculation:
        raise ValueError("An aggregate table plan requires calculation.")
    if (
        plan.operation == "aggregate"
        and plan.calculation != "count"
        and not plan.calculation_column
    ):
        raise ValueError(
            "A non-count aggregate table plan requires calculation_column."
        )


def execute_table_query_plan(
    plan: TableQueryPlan,
    table_store: TableArtifactStore,
    *,
    request_id: str,
) -> TableEvidence:
    """Execute a validated plan in Python and retain exact cell provenance."""

    if not request_id.strip():
        raise ValueError("request_id must be non-empty.")

    table = table_store.load_artifact(plan.artifact_id)
    _validate_executable_plan(plan, table)

    matched_indexes = [
        index
        for index, row in enumerate(table.rows)
        if _row_matches(table, index, row, plan.filters)
    ]
    warnings = list(table.warnings)
    if not matched_indexes:
        warnings.append("No table rows matched the query-plan filters.")
        return TableEvidence(
            request_id=request_id,
            artifact_id=plan.artifact_id,
            result_rows=[],
            source_cells=[],
            sufficient=False,
            warnings=warnings,
        )

    if plan.sort_column:
        matched_indexes = _sort_row_indexes(
            table,
            matched_indexes,
            plan.sort_column,
            descending=plan.sort_direction == "descending",
        )

    aggregate_warnings: list[str] = []
    if plan.operation == "aggregate":
        result_rows, calculation, aggregate_warnings = _aggregate_rows(
            table,
            matched_indexes,
            plan,
        )
        warnings.extend(aggregate_warnings)
        provenance_indexes = matched_indexes
    else:
        selected_indexes = (
            matched_indexes[: plan.limit]
            if plan.limit is not None
            else matched_indexes
        )
        result_rows = [
            {
                column: table.rows[index].get(column, "")
                for column in plan.selected_columns
            }
            for index in selected_indexes
        ]
        calculation = None
        provenance_indexes = selected_indexes

    provenance_columns = _provenance_columns(plan)
    source_cells, cell_details = _collect_cell_provenance(
        table,
        provenance_indexes,
        provenance_columns,
    )
    sufficient = bool(result_rows) and not aggregate_warnings
    return TableEvidence(
        request_id=request_id,
        artifact_id=plan.artifact_id,
        result_rows=result_rows,
        calculation=calculation,
        source_cells=source_cells,
        cell_details=cell_details,
        sufficient=sufficient,
        warnings=warnings,
    )


def _validate_executable_plan(
    plan: TableQueryPlan,
    table: NormalizedTable,
) -> None:
    """Revalidate a plan at the execution boundary."""

    known_columns = set(table.columns)
    referenced_columns = {
        *plan.selected_columns,
        *plan.filters.keys(),
        *plan.group_by,
    }
    for optional_column in (plan.sort_column, plan.calculation_column):
        if optional_column:
            referenced_columns.add(optional_column)
    unknown_columns = sorted(referenced_columns - known_columns)
    if unknown_columns:
        raise ValueError(
            f"Table query plan references unknown columns: {unknown_columns}."
        )
    if not plan.selected_columns:
        raise ValueError("Table query plan must select at least one column.")
    if plan.operation in {"sort", "timeline"} and not plan.sort_column:
        raise ValueError(
            f"A {plan.operation!r} table plan requires sort_column."
        )
    if plan.operation == "aggregate":
        if not plan.calculation:
            raise ValueError("An aggregate table plan requires calculation.")
        if plan.calculation != "count" and not plan.calculation_column:
            raise ValueError(
                "A non-count aggregate table plan requires calculation_column."
            )


def _row_matches(
    table: NormalizedTable,
    row_index: int,
    row: dict[str, str],
    filters: dict[str, str],
) -> bool:
    """Apply case-insensitive contains filters to text and semantic cell fields."""

    rich_row = table.row_cells[row_index] if row_index < len(table.row_cells) else {}
    for column, expected in filters.items():
        cell = rich_row.get(column)
        if cell is None:
            haystack = row.get(column, "")
        else:
            haystack = " ".join(
                [
                    cell.text,
                    cell.display_text,
                    *cell.bold_text,
                    *cell.italic_text,
                    *(annotation.text for annotation in cell.annotations),
                    *(annotation.note or "" for annotation in cell.annotations),
                    *cell.legend_matches,
                    cell.background_color or "",
                    cell.sort_value or "",
                ]
            )
        if _normalized_text(expected) not in _normalized_text(haystack):
            return False
    return True


def _sort_row_indexes(
    table: NormalizedTable,
    row_indexes: list[int],
    column: str,
    *,
    descending: bool,
) -> list[int]:
    present: list[int] = []
    missing: list[int] = []
    for index in row_indexes:
        value = _cell_sort_text(table, index, column)
        (present if value.strip() else missing).append(index)
    present.sort(
        key=lambda index: _sortable_value(_cell_sort_text(table, index, column)),
        reverse=descending,
    )
    return present + missing


def _cell_sort_text(
    table: NormalizedTable,
    row_index: int,
    column: str,
) -> str:
    if row_index < len(table.row_cells):
        cell = table.row_cells[row_index].get(column)
        if cell is not None and cell.sort_value:
            return cell.sort_value
    return table.rows[row_index].get(column, "")


def _sortable_value(value: str) -> tuple[int, float | str]:
    numeric = _parse_number(value)
    if numeric is not None:
        return (0, float(numeric))
    return (1, _normalized_text(value))


def _aggregate_rows(
    table: NormalizedTable,
    row_indexes: list[int],
    plan: TableQueryPlan,
) -> tuple[list[dict[str, str | int | float]], str | None, list[str]]:
    """Execute a supported aggregate, optionally grouped by exact columns."""

    groups: dict[tuple[str, ...], list[int]] = {}
    for index in row_indexes:
        key = tuple(table.rows[index].get(column, "") for column in plan.group_by)
        groups.setdefault(key, []).append(index)

    result_rows: list[dict[str, str | int | float]] = []
    warnings: list[str] = []
    for key, indexes in groups.items():
        result: dict[str, str | int | float] = {
            column: value
            for column, value in zip(plan.group_by, key, strict=True)
        }
        if plan.calculation == "count":
            result["count"] = len(indexes)
        else:
            column = plan.calculation_column
            if column is None:
                raise ValueError("calculation_column is required for this aggregate.")
            parsed_values = [
                _parse_number(table.rows[index].get(column, ""))
                for index in indexes
            ]
            numeric_values = [value for value in parsed_values if value is not None]
            if len(numeric_values) != len(parsed_values):
                warnings.append(
                    f"Could not parse every {column!r} value as numeric for "
                    f"{plan.calculation}."
                )
                continue
            aggregate_value: int | float
            if plan.calculation == "sum":
                aggregate_value = sum(numeric_values)
            elif plan.calculation == "min":
                aggregate_value = min(numeric_values)
            elif plan.calculation == "max":
                aggregate_value = max(numeric_values)
            elif plan.calculation == "average":
                aggregate_value = sum(numeric_values) / len(numeric_values)
            else:
                raise ValueError(f"Unsupported calculation: {plan.calculation}")
            result[f"{plan.calculation}_{column}"] = aggregate_value
        result_rows.append(result)

    if plan.limit is not None:
        result_rows = result_rows[: plan.limit]
    calculation = (
        plan.calculation
        if plan.calculation == "count"
        else f"{plan.calculation}({plan.calculation_column})"
    )
    return result_rows, calculation, warnings


def _provenance_columns(plan: TableQueryPlan) -> list[str]:
    columns = [
        *plan.selected_columns,
        *plan.filters.keys(),
        *plan.group_by,
    ]
    if plan.sort_column:
        columns.append(plan.sort_column)
    if plan.calculation_column:
        columns.append(plan.calculation_column)
    return list(dict.fromkeys(columns))


def _collect_cell_provenance(
    table: NormalizedTable,
    row_indexes: list[int],
    columns: list[str],
) -> tuple[list[str], list[TableCellEvidence]]:
    source_cells: list[str] = []
    details: list[TableCellEvidence] = []
    seen: set[str] = set()
    for row_index in row_indexes:
        if row_index >= len(table.row_cells):
            continue
        for column in columns:
            cell = table.row_cells[row_index].get(column)
            if cell is None:
                continue
            source_cell = (
                f"{table.table_id}:r{cell.origin_row + 1}:c{cell.origin_column + 1}"
            )
            if source_cell in seen:
                continue
            seen.add(source_cell)
            source_cells.append(source_cell)
            details.append(
                TableCellEvidence(
                    source_cell=source_cell,
                    row_number=row_index + 1,
                    column=column,
                    text=cell.text,
                    display_text=cell.display_text,
                    is_bold=cell.is_bold,
                    is_italic=cell.is_italic,
                    bold_text=cell.bold_text,
                    italic_text=cell.italic_text,
                    annotations=[
                        annotation.model_dump(mode="json")
                        for annotation in cell.annotations
                    ],
                    background_color=cell.background_color,
                    sort_value=cell.sort_value,
                    legend_matches=cell.legend_matches,
                )
            )
    return source_cells, details


def _parse_number(value: str) -> int | float | None:
    normalized = value.strip().replace(",", "").replace("$", "")
    normalized = normalized.removesuffix("%").strip("*†‡ ")
    negative = normalized.startswith("(") and normalized.endswith(")")
    if negative:
        normalized = normalized[1:-1].strip()
    if not re.fullmatch(r"[-+]?\d+(?:\.\d+)?", normalized):
        return None
    parsed = float(normalized)
    if negative:
        parsed = -parsed
    return int(parsed) if parsed.is_integer() else parsed


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _table_planner_context(
    entry: TableCatalogEntry,
    table: NormalizedTable,
    request: TableRequest,
    *,
    sample_rows: int,
) -> dict[str, object]:
    """Create a compact, query-focused view without discarding rich cell cues."""

    query_text = " ".join(
        [
            request.missing_fact,
            *request.columns_needed,
            *request.row_filters.keys(),
            *request.row_filters.values(),
            request.comparison_key or "",
        ]
    )
    query_tokens = _search_tokens(query_text)
    ranked_rows: list[tuple[int, int]] = []
    for index, row in enumerate(table.rows):
        row_tokens = _search_tokens(" ".join(row.values()))
        ranked_rows.append((len(query_tokens & row_tokens), index))
    ranked_rows.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    selected_indexes = [index for _, index in ranked_rows[:sample_rows]]

    samples: list[dict[str, object]] = []
    for index in selected_indexes:
        semantic_signals: dict[str, dict[str, object]] = {}
        if index < len(table.row_cells):
            for column, cell in table.row_cells[index].items():
                signals = {
                    "bold_text": cell.bold_text,
                    "italic_text": cell.italic_text,
                    "annotations": [
                        annotation.model_dump(mode="json")
                        for annotation in cell.annotations
                    ],
                    "background_color": cell.background_color,
                    "legend_matches": cell.legend_matches,
                }
                if any(signals.values()):
                    semantic_signals[column] = signals
        samples.append(
            {
                "row_number": index + 1,
                "values": table.rows[index],
                "semantic_signals": semantic_signals,
            }
        )

    return {
        "artifact_id": entry.artifact_id,
        "source_article": entry.source_article,
        "table_id": entry.table_id,
        "caption": entry.caption,
        "section_path": entry.section_path,
        "columns": entry.columns,
        "row_count": entry.row_count,
        "legends": [legend.model_dump(mode="json") for legend in table.legends],
        "sample_rows": samples,
    }


def _article_key(value: str) -> str:
    """Canonical comparison key for an article filename or display label."""

    name = Path(value.strip()).name
    if name.casefold().endswith(".html"):
        name = name[:-5]
    return "_".join(name.replace("_", " ").split()).casefold()


def _search_tokens(value: str) -> set[str]:
    """Return small, comparison-oriented tokens without adding an NLP dependency."""

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
    stop_words = {
        "a",
        "an",
        "and",
        "for",
        "in",
        "is",
        "of",
        "the",
        "to",
        "was",
        "were",
        "which",
        "who",
    }
    tokens: set[str] = set()
    for raw_token in re.findall(r"\w+", value.casefold()):
        token = aliases.get(raw_token, raw_token)
        if len(token) > 1 and token not in stop_words:
            tokens.add(token)
    return tokens
