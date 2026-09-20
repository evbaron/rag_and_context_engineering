"""Normalize Wikipedia HTML tables without discarding their semantic markup.

Wikipedia tables frequently encode meaning outside the visible cell text:

* ``rowspan`` and ``colspan`` establish row/column relationships;
* ``<sup>`` / ``<sub>`` contain note references or semantic markers;
* bold/italic text and background colors distinguish winners or special rows; and
* nearby legends explain symbols (``†``) and abbreviations (``QB``).

The project's original sidecar extractor intentionally emits a compact
``headers``/``rows`` representation. This module is the richer representation for
the Checkpoint 5.1 table-analysis branch. It keeps a convenient list of string
dictionaries in ``NormalizedTable.rows`` while exposing cell metadata in
``NormalizedTable.row_cells``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup, NavigableString, Tag
from pydantic import BaseModel, Field


PARSER_VERSION = "1"
DEFAULT_TABLE_SELECTOR = "table.wikitable"

_WHITESPACE = re.compile(r"\s+")
_HEADING_TAG = re.compile(r"^h([2-6])$")
_BACKGROUND = re.compile(
    r"(?:^|;)\s*background(?:-color)?\s*:\s*([^;]+)", re.IGNORECASE
)
_FONT_WEIGHT_BOLD = re.compile(
    r"font-weight\s*:\s*(?:bold|[6-9]00)", re.IGNORECASE
)
_SEPARATOR = re.compile(r"\s*(?:—|–|-)\s*")
_NON_WORD_SYMBOL = re.compile(r"^[^\w\s]+$", re.UNICODE)


class CellAnnotation(BaseModel):
    """Superscript/subscript content retained separately from base cell text."""

    position: Literal["superscript", "subscript"]
    text: str
    role: Literal["reference", "marker"]
    target: str | None = None
    note: str | None = None


class CellLink(BaseModel):
    """A link contained in a cell."""

    text: str
    href: str
    title: str | None = None


class TableLegend(BaseModel):
    """A page-level visual or symbolic convention applicable to table cells."""

    kind: Literal["symbol", "abbreviation", "color"]
    meaning: str
    symbol: str | None = None
    color: str | None = None
    annotations: list[CellAnnotation] = Field(default_factory=list)


class NormalizedCell(BaseModel):
    """A cell after span expansion, with its original presentation semantics."""

    # ``text`` excludes superscripts/subscripts; ``display_text`` includes them.
    text: str
    display_text: str
    is_header: bool
    is_bold: bool = False
    is_italic: bool = False
    bold_text: list[str] = Field(default_factory=list)
    italic_text: list[str] = Field(default_factory=list)
    annotations: list[CellAnnotation] = Field(default_factory=list)
    links: list[CellLink] = Field(default_factory=list)
    background_color: str | None = None
    sort_value: str | None = None
    legend_matches: list[str] = Field(default_factory=list)

    # Coordinates refer to the expanded table grid. Span copies retain the origin.
    origin_row: int
    origin_column: int
    row_span: int = 1
    column_span: int = 1
    inherited: bool = False


class NormalizedTable(BaseModel):
    artifact_id: str
    source_article: str
    table_id: str
    caption: str | None
    section_path: list[str]
    columns: list[str]
    rows: list[dict[str, str]]
    warnings: list[str]
    source_hash: str
    parser_version: str

    # Rich fields used by the table-analysis agent.
    header_rows: list[list[str]] = Field(default_factory=list)
    row_cells: list[dict[str, NormalizedCell]] = Field(default_factory=list)
    legends: list[TableLegend] = Field(default_factory=list)
    context_before: str | None = None
    html_hash: str
    classes: list[str] = Field(default_factory=list)
    table_role: Literal["data", "legend"] = "data"


def _clean_text(value: str) -> str:
    """Collapse Wikipedia/HTML whitespace while retaining visible punctuation."""

    return _WHITESPACE.sub(" ", value.replace("\xa0", " ")).strip()


def _text_without_annotations(element: Tag) -> str:
    """Return visible text, excluding text nested in ``sup`` or ``sub`` tags."""

    parts: list[str] = []
    for node in element.descendants:
        if not isinstance(node, NavigableString):
            continue
        if any(
            isinstance(parent, Tag)
            and parent.name in {"sup", "sub", "script", "style"}
            for parent in node.parents
            if parent is not element
        ):
            continue
        parts.append(str(node))
    return _clean_text(" ".join(parts))


def _direct_rows(table: Tag) -> list[Tag]:
    """Return rows owned by ``table``, excluding rows of nested layout tables."""

    return [
        row
        for row in table.find_all("tr")
        if row.find_parent("table") is table
    ]


def _direct_cells(row: Tag) -> list[Tag]:
    return [cell for cell in row.find_all(["th", "td"], recursive=False)]


def _positive_span(cell: Tag, attribute: str) -> int:
    try:
        return max(1, int(cell.get(attribute, 1)))
    except (TypeError, ValueError):
        return 1


def _normalize_color(value: str | None) -> str | None:
    if not value:
        return None
    color = _clean_text(value).lower().replace(" ", "")
    if re.fullmatch(r"#[0-9a-f]{3}", color):
        color = "#" + "".join(character * 2 for character in color[1:])
    return color or None


def _background_color(cell: Tag) -> str | None:
    """Read effective cell/row background color (cell takes precedence)."""

    for element in (cell, cell.find_parent("tr")):
        if not isinstance(element, Tag):
            continue
        if color := _normalize_color(element.get("bgcolor")):
            return color
        if match := _BACKGROUND.search(element.get("style", "")):
            return _normalize_color(match.group(1))
    return None


def _note_lookup(soup: BeautifulSoup) -> dict[str, str]:
    notes: dict[str, str] = {}
    targets = {
        anchor["href"].removeprefix("#")
        for annotation in soup.find_all(["sup", "sub"])
        for anchor in annotation.find_all("a", href=True)
        if anchor["href"].startswith("#")
    }
    for target in targets:
        element = soup.find(id=target)
        if not isinstance(element, Tag):
            continue
        clone = BeautifulSoup(str(element), "lxml")
        for backlink in clone.select(".mw-cite-backlink"):
            backlink.decompose()
        notes[target] = _clean_text(clone.get_text(" ", strip=True))
    return notes


def _annotations(element: Tag, notes: dict[str, str]) -> list[CellAnnotation]:
    annotations: list[CellAnnotation] = []
    for annotation in element.find_all(["sup", "sub"]):
        text = _clean_text(annotation.get_text(" ", strip=True))
        if not text:
            continue
        link = annotation.find("a", href=True)
        target = link["href"].removeprefix("#") if link else None
        is_reference = bool("reference" in annotation.get("class", []) or target)
        annotations.append(
            CellAnnotation(
                position="superscript" if annotation.name == "sup" else "subscript",
                text=text,
                role="reference" if is_reference else "marker",
                target=target,
                note=notes.get(target) if target else None,
            )
        )
    return annotations


def _links(element: Tag) -> list[CellLink]:
    links: list[CellLink] = []
    seen: set[tuple[str, str]] = set()
    for anchor in element.find_all("a", href=True):
        text = _clean_text(anchor.get_text(" ", strip=True))
        key = (text, anchor["href"])
        if key in seen:
            continue
        seen.add(key)
        links.append(
            CellLink(text=text, href=anchor["href"], title=anchor.get("title"))
        )
    return links


def _styled_text(element: Tag, names: Iterable[str]) -> list[str]:
    values: list[str] = []
    for child in element.find_all(list(names)):
        value = _clean_text(child.get_text(" ", strip=True))
        if value and value not in values:
            values.append(value)
    return values


def _parse_cell(
    element: Tag,
    *,
    row_index: int,
    column_index: int,
    notes: dict[str, str],
) -> NormalizedCell:
    style = element.get("style", "")
    bold_text = _styled_text(element, ("b", "strong"))
    italic_text = _styled_text(element, ("i", "em"))
    sort_element = element.find(attrs={"data-sort-value": True})
    return NormalizedCell(
        text=_text_without_annotations(element),
        display_text=_clean_text(element.get_text(" ", strip=True)),
        is_header=element.name == "th",
        is_bold=bool(bold_text or _FONT_WEIGHT_BOLD.search(style)),
        is_italic=bool(italic_text),
        bold_text=bold_text,
        italic_text=italic_text,
        annotations=_annotations(element, notes),
        links=_links(element),
        background_color=_background_color(element),
        sort_value=(
            element.get("data-sort-value")
            or (sort_element.get("data-sort-value") if sort_element else None)
        ),
        origin_row=row_index,
        origin_column=column_index,
        row_span=_positive_span(element, "rowspan"),
        column_span=_positive_span(element, "colspan"),
    )


def _expanded_grid(
    table: Tag,
    notes: dict[str, str],
) -> tuple[list[list[NormalizedCell | None]], bool]:
    """Expand row/column spans into a rectangular logical grid."""

    rows = _direct_rows(table)
    grid_maps: list[dict[int, NormalizedCell]] = []
    # column -> (origin cell, number of additional rows still to fill)
    pending: dict[int, tuple[NormalizedCell, int]] = {}
    used_spans = False

    for row_index, row in enumerate(rows):
        row_map: dict[int, NormalizedCell] = {}
        next_pending: dict[int, tuple[NormalizedCell, int]] = {}
        for column, (cell, remaining) in sorted(pending.items()):
            row_map[column] = cell.model_copy(update={"inherited": True})
            if remaining > 1:
                next_pending[column] = (cell, remaining - 1)

        cursor = 0
        for element in _direct_cells(row):
            column_span = _positive_span(element, "colspan")
            while any(column in row_map for column in range(cursor, cursor + column_span)):
                cursor += 1

            cell = _parse_cell(
                element,
                row_index=row_index,
                column_index=cursor,
                notes=notes,
            )
            used_spans = used_spans or cell.row_span > 1 or cell.column_span > 1
            for offset in range(cell.column_span):
                column = cursor + offset
                row_map[column] = (
                    cell if offset == 0 else cell.model_copy(update={"inherited": True})
                )
                if cell.row_span > 1:
                    next_pending[column] = (cell, cell.row_span - 1)
            cursor += cell.column_span

        grid_maps.append(row_map)
        pending = next_pending

    width = max((max(row, default=-1) + 1 for row in grid_maps), default=0)
    grid = [[row.get(column) for column in range(width)] for row in grid_maps]
    return grid, used_spans


def _header_row_count(table: Tag, grid: list[list[NormalizedCell | None]]) -> int:
    rows = _direct_rows(table)
    explicit = sum(
        1
        for row in rows
        if row.find_parent("thead") is not None
        and row.find_parent("thead").find_parent("table") is table
    )
    if explicit:
        return explicit

    count = 0
    for row in rows:
        cells = _direct_cells(row)
        if cells and all(cell.name == "th" for cell in cells):
            count += 1
        else:
            break
    return min(count, len(grid))


def _deduplicate_columns(columns: list[str]) -> tuple[list[str], bool]:
    result: list[str] = []
    counts: dict[str, int] = {}
    changed = False
    for index, original in enumerate(columns, 1):
        base = original or f"column_{index}"
        counts[base] = counts.get(base, 0) + 1
        value = base if counts[base] == 1 else f"{base}__{counts[base]}"
        changed = changed or value != original
        result.append(value)
    return result, changed


def _columns_from_headers(
    grid: list[list[NormalizedCell | None]],
    header_count: int,
) -> tuple[list[str], list[list[str]], bool]:
    width = len(grid[0]) if grid else 0
    header_rows = [
        [cell.text if cell else "" for cell in row]
        for row in grid[:header_count]
    ]
    if not header_rows:
        return [f"column_{index}" for index in range(1, width + 1)], [], False

    columns: list[str] = []
    for column in range(width):
        parts: list[str] = []
        for row in header_rows:
            part = row[column]
            if part and (not parts or part != parts[-1]):
                parts.append(part)
        columns.append(" / ".join(parts))
    columns, changed = _deduplicate_columns(columns)
    return columns, header_rows, changed


def _style_color(element: Tag | None) -> str | None:
    if not isinstance(element, Tag):
        return None
    if match := _BACKGROUND.search(element.get("style", "")):
        return _normalize_color(match.group(1))
    return _normalize_color(element.get("bgcolor"))


def _extract_legends(root: Tag, notes: dict[str, str]) -> list[TableLegend]:
    """Extract color keys, small symbol-key tables, and abbreviation lists."""

    legends: list[TableLegend] = []

    # Wikipedia's Template:Legend renders this structure.
    for element in root.select("div.legend"):
        color_element = element.select_one(".legend-color")
        color = _style_color(color_element)
        if not color:
            continue
        clone = BeautifulSoup(str(element), "lxml")
        for swatch in clone.select(".legend-color"):
            swatch.decompose()
        meaning = _clean_text(clone.get_text(" ", strip=True))
        if meaning:
            legends.append(TableLegend(kind="color", color=color, meaning=meaning))

    # Small two-column tables are commonly used as symbol keys. Use direct rows so
    # a surrounding layout table does not absorb its nested position-key table.
    for table in root.find_all("table"):
        rows = _direct_rows(table)
        if not rows or len(rows) > 12:
            continue
        for row in rows:
            cells = _direct_cells(row)
            if len(cells) < 2:
                continue
            symbol = _text_without_annotations(cells[0])
            meaning = _text_without_annotations(cells[1])
            if not symbol or not meaning or len(symbol) > 12:
                continue
            # Symbol-key tables use punctuation/glyph markers. Short alphanumeric
            # values (for example draft pick ``1``) are ordinary table data and
            # must not become accidental page-wide legends.
            if not _NON_WORD_SYMBOL.fullmatch(symbol):
                continue
            legends.append(
                TableLegend(
                    kind="symbol",
                    symbol=symbol,
                    color=_background_color(cells[0]),
                    meaning=meaning,
                    annotations=_annotations(cells[1], notes),
                )
            )

    # Position keys and similar glossaries often use ``<li><b>QB</b> — ...``.
    for item in root.find_all("li"):
        parent_table = item.find_parent("table")
        caption = parent_table.find("caption") if parent_table else None
        if not caption or "key" not in _clean_text(
            caption.get_text(" ", strip=True)
        ).casefold():
            continue
        bold = item.find(["b", "strong"])
        if not bold:
            continue
        symbol = _text_without_annotations(bold)
        text = _text_without_annotations(item)
        if not symbol or len(symbol) > 12 or not text.startswith(symbol):
            continue
        remainder = text[len(symbol) :].strip()
        remainder = _SEPARATOR.sub("", remainder, count=1).strip()
        if not remainder or remainder == text:
            continue
        legends.append(
            TableLegend(
                kind="abbreviation",
                symbol=symbol,
                meaning=remainder,
                annotations=_annotations(item, notes),
            )
        )

    unique: list[TableLegend] = []
    seen: set[tuple[str, str | None, str | None, str]] = set()
    for legend in legends:
        key = (legend.kind, legend.symbol, legend.color, legend.meaning.casefold())
        if key not in seen:
            seen.add(key)
            unique.append(legend)
    return unique


def _symbol_present(symbol: str, cell: NormalizedCell) -> bool:
    if any(annotation.text == symbol for annotation in cell.annotations):
        return True
    if symbol.isalnum():
        return cell.text.casefold() == symbol.casefold()
    # Glyph markers are often attached directly to a value (``1*``, ``Name‡``),
    # so word-boundary matching would miss them.
    return symbol in cell.display_text


def _apply_legends(
    cell: NormalizedCell,
    legends: list[TableLegend],
) -> NormalizedCell:
    matches: list[str] = []
    for legend in legends:
        matched = bool(
            legend.kind == "color"
            and legend.color
            and legend.color == cell.background_color
        )
        if legend.symbol and _symbol_present(legend.symbol, cell):
            same_symbol = [item for item in legends if item.symbol == legend.symbol]
            has_color_variants = len(same_symbol) > 1 and any(
                item.color is not None for item in same_symbol
            )
            # Some Academy keys reuse † for two meanings and distinguish them only
            # by the key row's background color. In that case None means an
            # uncolored cell; it is not a wildcard.
            matched = (
                legend.color == cell.background_color
                if has_color_variants
                else True
            )
        if matched and legend.meaning not in matches:
            matches.append(legend.meaning)
    return cell.model_copy(update={"legend_matches": matches})


def _section_path(table: Tag) -> list[str]:
    headings = [
        heading
        for heading in reversed(table.find_all_previous(_HEADING_TAG))
        if heading.find_parent("table") is None
    ]
    path: list[str] = []
    levels: list[int] = []
    for heading in headings:
        match = _HEADING_TAG.match(heading.name or "")
        if not match:
            continue
        level = int(match.group(1))
        title = _clean_text(heading.get_text(" ", strip=True))
        title = re.sub(r"\[\s*edit\s*\]$", "", title, flags=re.IGNORECASE).strip()
        while levels and levels[-1] >= level:
            levels.pop()
            path.pop()
        if title:
            levels.append(level)
            path.append(title)
    return path


def _context_before(table: Tag, max_characters: int = 800) -> str | None:
    pieces: list[str] = []
    size = 0
    sibling = table.find_previous_sibling()
    while sibling is not None and size < max_characters:
        if isinstance(sibling, Tag) and _HEADING_TAG.match(sibling.name or ""):
            break
        if isinstance(sibling, Tag) and sibling.name in {"p", "div"}:
            text = _clean_text(sibling.get_text(" ", strip=True))
            if text and not text.startswith("@media"):
                pieces.append(text)
                size += len(text)
        sibling = sibling.find_previous_sibling()
    if not pieces:
        return None
    return " ".join(reversed(pieces))[-max_characters:]


def _table_signature(table: Tag, caption: str | None) -> str:
    rows = _direct_rows(table)
    sample = "|".join(
        _clean_text(cell.get_text(" ", strip=True))
        for row in rows[:3]
        for cell in _direct_cells(row)
    )
    return hashlib.sha256(f"{caption or ''}|{sample}".encode()).hexdigest()[:10]


def _relevant_legends(
    grid: list[list[NormalizedCell | None]],
    legends: list[TableLegend],
) -> list[TableLegend]:
    cells = [cell for row in grid for cell in row if cell is not None]
    relevant: list[TableLegend] = []
    for legend in legends:
        if legend.color and any(cell.background_color == legend.color for cell in cells):
            relevant.append(legend)
        elif legend.symbol and any(_symbol_present(legend.symbol, cell) for cell in cells):
            relevant.append(legend)
        elif legend.kind == "abbreviation" and legend.symbol:
            if any(cell.text.casefold() == legend.symbol.casefold() for cell in cells):
                relevant.append(legend)
    return relevant


def _normalize_table(
    table: Tag,
    *,
    table_index: int,
    source_article: str,
    source_hash: str,
    notes: dict[str, str],
    page_legends: list[TableLegend],
) -> NormalizedTable:
    caption_element = table.find("caption", recursive=False)
    caption = (
        _text_without_annotations(caption_element) if caption_element else None
    ) or None
    grid, used_spans = _expanded_grid(table, notes)
    header_count = _header_row_count(table, grid)
    columns, header_rows, renamed_columns = _columns_from_headers(grid, header_count)
    relevant_legends = _relevant_legends(grid, page_legends)

    rows: list[dict[str, str]] = []
    row_cells: list[dict[str, NormalizedCell]] = []
    for grid_row in grid[header_count:]:
        rich_row: dict[str, NormalizedCell] = {}
        text_row: dict[str, str] = {}
        for column_index, column in enumerate(columns):
            cell = grid_row[column_index] if column_index < len(grid_row) else None
            if cell is None:
                continue
            enriched = _apply_legends(cell, relevant_legends)
            rich_row[column] = enriched
            text_row[column] = enriched.text
        if any(value for value in text_row.values()):
            rows.append(text_row)
            row_cells.append(rich_row)

    warnings: list[str] = []
    if not header_count:
        warnings.append("No explicit header row detected; generated positional columns.")
    if renamed_columns:
        warnings.append("Blank or duplicate column names were made unique.")
    if used_spans:
        warnings.append("Expanded rowspan/colspan values into the logical grid.")
    if any(cell.annotations for row in row_cells for cell in row.values()):
        warnings.append("Superscript/subscript annotations are available in row_cells.")
    if not rows:
        warnings.append("No non-empty data rows were found.")

    html_hash = hashlib.sha256(str(table).encode()).hexdigest()
    signature = _table_signature(table, caption)
    table_id = f"table-{table_index:03d}-{signature}"
    artifact_id = hashlib.sha256(
        f"{source_hash}:{table_id}:{PARSER_VERSION}".encode()
    ).hexdigest()[:24]

    return NormalizedTable(
        artifact_id=artifact_id,
        source_article=source_article,
        table_id=table_id,
        caption=caption,
        section_path=_section_path(table),
        columns=columns,
        rows=rows,
        warnings=warnings,
        source_hash=source_hash,
        parser_version=PARSER_VERSION,
        header_rows=header_rows,
        row_cells=row_cells,
        legends=relevant_legends,
        context_before=_context_before(table),
        html_hash=html_hash,
        classes=list(table.get("class", [])),
        table_role=(
            "legend"
            if caption and "key" in caption.casefold()
            else "data"
        ),
    )


def parse_wikipedia_html(
    html: str,
    *,
    source_article: str,
    table_selector: str = DEFAULT_TABLE_SELECTOR,
) -> list[NormalizedTable]:
    """Parse selected tables from one Wikipedia HTML document.

    The default selects semantic Wikipedia ``wikitable`` tables and excludes
    infoboxes, navigation boxes, and outer layout tables. Pass ``"table"`` only
    when the caller intentionally wants every HTML table.
    """

    soup = BeautifulSoup(html, "lxml")
    roots = soup.select("div.mw-parser-output")
    root: Tag = max(roots, key=lambda element: len(element.get_text())) if roots else soup
    notes = _note_lookup(soup)
    legends = _extract_legends(root, notes)
    source_hash = hashlib.sha256(html.encode()).hexdigest()

    return [
        _normalize_table(
            table,
            table_index=index,
            source_article=source_article,
            source_hash=source_hash,
            notes=notes,
            page_legends=legends,
        )
        for index, table in enumerate(root.select(table_selector), 1)
    ]


def parse_wikipedia_file(
    path: str | Path,
    *,
    table_selector: str = DEFAULT_TABLE_SELECTOR,
) -> list[NormalizedTable]:
    """Read and normalize tables from a local Wikipedia HTML file."""

    source_path = Path(path)
    html = source_path.read_text(encoding="utf-8", errors="replace")
    return parse_wikipedia_html(
        html,
        source_article=source_path.name,
        table_selector=table_selector,
    )


# Friendly alias for graph nodes that do not care whether the source is a file.
parse_wikipedia_tables = parse_wikipedia_file


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize semantic tables from a Wikipedia HTML file."
    )
    parser.add_argument("html_file", type=Path)
    parser.add_argument(
        "--all-tables",
        action="store_true",
        help="Include infobox/layout/navigation tables (normally excluded).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON to this path instead of standard output.",
    )
    args = parser.parse_args()
    tables = parse_wikipedia_file(
        args.html_file,
        table_selector="table" if args.all_tables else DEFAULT_TABLE_SELECTOR,
    )
    payload = json.dumps(
        [table.model_dump(mode="json") for table in tables],
        indent=2,
        ensure_ascii=False,
    )
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    _main()
