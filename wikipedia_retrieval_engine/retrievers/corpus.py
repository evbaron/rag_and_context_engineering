"""Load Wikipedia HTML articles into text chunks for BM25 / vector / hybrid retrieval."""
from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WIKI_DIR = ENGINE_ROOT / "Wikipedia"
DEFAULT_CHROMA_DB_ROOT = Path(__file__).resolve().parent / "db"
DEFAULT_CHROMA_DB_NAME = "wikipedia"
DEFAULT_CHROMA_DIR = DEFAULT_CHROMA_DB_ROOT / DEFAULT_CHROMA_DB_NAME

CHUNK_SIZE = 1600
CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class WikiChunk:
    doc_id: str
    source: str
    title: str
    text: str
    chunk_index: int


class _HTMLTextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP_TAGS:
            self._skip += 1
        elif tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "dt", "dd"}:
            if not self._skip:
                self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip:
            self._skip -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "section"} and not self._skip:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._parts.append(data)

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"\[edit\]", "", raw, flags=re.I)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r" *\n *", "\n", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(markup: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(markup)
    parser.close()
    return parser.text()


def extract_title_and_body(raw: str) -> tuple[str, str]:
    title_m = re.search(
        r'class="mw-page-title-main"[^>]*>(.*?)</span>', raw, flags=re.I | re.S
    )
    if title_m:
        title = html_lib.unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip()
    else:
        title_m = re.search(r"<title>(.*?)</title>", raw, flags=re.I | re.S)
        title = html_lib.unescape(title_m.group(1)).replace(" - Wikipedia", "").strip() if title_m else ""

    start = raw.find('id="mw-content-text"')
    if start != -1:
        gt = raw.find(">", start)
        body = raw[gt + 1 :] if gt != -1 else raw[start:]
    else:
        body = raw
    for marker in ('id="References"', 'id="Notes"', 'class="printfooter"'):
        cut = body.find(marker)
        if cut != -1:
            body = body[:cut]
            break
    return title, html_to_text(body)


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            window = text[start:end]
            br = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
            if br >= chunk_size // 3:
                end = start + br + (1 if window[br] == "." else 0)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def load_wikipedia_chunks(
    wiki_dir: str | Path | None = None,
    *,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    filenames: list[str] | None = None,
    max_files: int | None = None,
) -> list[WikiChunk]:
    """Parse Wikipedia HTML files into overlapping text chunks."""
    root = Path(wiki_dir) if wiki_dir else DEFAULT_WIKI_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"Wikipedia corpus not found: {root}")

    if filenames:
        paths = [root / name for name in filenames]
    else:
        paths = sorted(
            p for p in root.iterdir()
            if p.suffix.lower() == ".html" and not p.name.startswith("_")
        )
        if max_files is not None:
            paths = paths[:max_files]

    chunks: list[WikiChunk] = []
    for path in paths:
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        title, body = extract_title_and_body(raw)
        title = title or path.stem.replace("_", " ")
        parts = chunk_text(body, chunk_size=chunk_size, overlap=overlap)
        for i, part in enumerate(parts):
            chunks.append(
                WikiChunk(
                    doc_id=f"{path.name}#{i}",
                    source=path.name,
                    title=title,
                    text=part,
                    chunk_index=i,
                )
            )
    return chunks
