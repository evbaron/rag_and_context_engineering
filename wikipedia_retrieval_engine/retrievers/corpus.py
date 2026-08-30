"""Load Wikipedia HTML articles into text chunks for BM25 / vector / hybrid retrieval."""
from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WIKI_DIR = ENGINE_ROOT / "Wikipedia"
DEFAULT_CHROMA_DB_ROOT = Path(__file__).resolve().parent / "db"
DEFAULT_CHROMA_DB_NAME = "wikipedia"
DEFAULT_CHROMA_DIR = DEFAULT_CHROMA_DB_ROOT / DEFAULT_CHROMA_DB_NAME
DEFAULT_ARTICLE_TEXT_ROOT = Path(__file__).resolve().parent / "db" / "article_text"
DEFAULT_ARTICLE_TEXT_NAME = "wikipedia_plain_text"

CHUNK_SIZE = 1600
CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class WikiChunk:
    doc_id: str
    source: str
    title: str
    text: str
    chunk_index: int
    section_title: str = ""
    section_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class ArticleText:
    """One complete extracted article loaded from its persistent text file."""

    source: str
    title: str
    text: str
    path: Path


class ArticleTextStore:
    """Lazy access to one plain-text file per Wikipedia article."""

    def __init__(self, root: Path, titles: dict[str, str]) -> None:
        self.root = root
        self._titles = titles

    def __len__(self) -> int:
        return len(self._titles)

    def has_article(self, source: str) -> bool:
        return source in self._titles

    def load(self, source: str) -> ArticleText:
        if source not in self._titles:
            raise KeyError(f"Extracted article is not available: {source}")
        path = self.root / f"{source}.txt"
        return ArticleText(
            source=source,
            title=self._titles[source],
            text=path.read_text(encoding="utf-8"),
            path=path,
        )


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


class _HTMLSectionExtractor(HTMLParser):
    """Extract body text while preserving the h2–h6 section hierarchy."""

    SKIP_TAGS = {"script", "style", "noscript", "svg"}
    BLOCK_TAGS = {
        "p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
        "dt", "dd",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._heading_level: int | None = None
        self._heading_parts: list[str] = []
        self._body_parts: list[str] = []
        self._path: list[str] = []
        self._sections: list[tuple[tuple[str, ...], str]] = []

    @staticmethod
    def _clean(parts: list[str]) -> str:
        text = "".join(parts)
        text = re.sub(r"\[edit\]", "", text, flags=re.I)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r" *\n *", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _flush_body(self) -> None:
        text = self._clean(self._body_parts)
        if text:
            self._sections.append((tuple(self._path), text))
        self._body_parts = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.SKIP_TAGS:
            self._skip += 1
            return
        if self._skip:
            return
        if tag in {"h2", "h3", "h4", "h5", "h6"}:
            self._flush_body()
            self._heading_level = int(tag[1])
            self._heading_parts = []
        elif tag in self.BLOCK_TAGS:
            self._body_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip:
            self._skip -= 1
            return
        if self._skip:
            return
        if tag in {"h2", "h3", "h4", "h5", "h6"} and self._heading_level:
            heading = self._clean(self._heading_parts)
            depth = self._heading_level - 1  # h2 is the first section level.
            self._path = self._path[: depth - 1]
            if heading:
                self._path.append(heading)
            self._heading_level = None
            self._heading_parts = []
        elif tag in self.BLOCK_TAGS:
            self._body_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._heading_level is not None:
            self._heading_parts.append(data)
        else:
            self._body_parts.append(data)

    def sections(self) -> list[tuple[tuple[str, ...], str]]:
        self._flush_body()
        return self._sections


def html_to_text(markup: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(markup)
    parser.close()
    return parser.text()


def _article_body_markup(raw: str) -> str:
    """Return article-body HTML before references/notes/footer content."""
    start = raw.find('id="mw-content-text"')
    if start != -1:
        gt = raw.find(">", start)
        body = raw[gt + 1 :] if gt != -1 else raw[start:]
    else:
        body = raw
    cuts = [
        cut
        for marker in ('id="References"', 'id="Notes"', 'class="printfooter"')
        if (cut := body.find(marker)) != -1
    ]
    return body[: min(cuts)] if cuts else body


def extract_title_and_body(raw: str) -> tuple[str, str]:
    title_m = re.search(
        r'class="mw-page-title-main"[^>]*>(.*?)</span>', raw, flags=re.I | re.S
    )
    if title_m:
        title = html_lib.unescape(re.sub(r"<[^>]+>", "", title_m.group(1))).strip()
    else:
        title_m = re.search(r"<title>(.*?)</title>", raw, flags=re.I | re.S)
        title = html_lib.unescape(title_m.group(1)).replace(" - Wikipedia", "").strip() if title_m else ""

    return title, html_to_text(_article_body_markup(raw))


def extract_title_and_sections(raw: str) -> tuple[str, list[tuple[tuple[str, ...], str]]]:
    """Extract an article title and natural sections based on h2–h6 headings."""
    title, _ = extract_title_and_body(raw)
    parser = _HTMLSectionExtractor()
    parser.feed(_article_body_markup(raw))
    parser.close()
    sections = [(("Lead",) if not path else path, text) for path, text in parser.sections()]
    return title, sections


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


def load_wikipedia_section_chunks(
    wiki_dir: str | Path | None = None,
    *,
    max_section_chars: int = 4000,
    overlap: int = CHUNK_OVERLAP,
    filenames: list[str] | None = None,
    max_files: int | None = None,
) -> list[WikiChunk]:
    """Create natural chunks from article headings, splitting only oversized sections."""
    root = Path(wiki_dir) if wiki_dir else DEFAULT_WIKI_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"Wikipedia corpus not found: {root}")
    if filenames:
        paths = [root / name for name in filenames]
    else:
        paths = sorted(
            path
            for path in root.iterdir()
            if path.suffix.lower() == ".html" and not path.name.startswith("_")
        )
        if max_files is not None:
            paths = paths[:max_files]

    chunks: list[WikiChunk] = []
    article_chunk_index = 0
    for path in paths:
        if not path.is_file():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        title, sections = extract_title_and_sections(raw)
        title = title or path.stem.replace("_", " ")
        article_chunk_index = 0
        for section_index, (section_path, section_text) in enumerate(sections):
            section_label = " > ".join(section_path)
            prefix = f"Article: {title}\nSection: {section_label}\n\n"
            available_chars = max(max_section_chars - len(prefix), 500)
            parts = chunk_text(section_text, chunk_size=available_chars, overlap=overlap)
            for part_index, part in enumerate(parts):
                chunks.append(
                    WikiChunk(
                        doc_id=(
                            f"{path.name}#section-{section_index:03d}-{part_index:02d}"
                        ),
                        source=path.name,
                        title=title,
                        text=prefix + part,
                        chunk_index=article_chunk_index,
                        section_title=section_path[-1],
                        section_path=section_path,
                    )
                )
                article_chunk_index += 1
    return chunks


_VALID_CACHE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_ARTICLE_TEXT_EXTRACTOR_VERSION = 1


def article_text_store_path(
    text_store_name: str = DEFAULT_ARTICLE_TEXT_NAME,
) -> Path:
    """Resolve ``retrievers/db/article_text/<name>`` safely."""
    if not _VALID_CACHE_NAME.fullmatch(text_store_name) or text_store_name in {".", ".."}:
        raise ValueError(
            "text_store_name must contain only letters, numbers, '.', '_', or '-', "
            "must start with a letter or number, and cannot be a path."
        )
    return DEFAULT_ARTICLE_TEXT_ROOT / text_store_name


def build_or_load_article_text_store(
    wiki_dir: str | Path | None = None,
    *,
    text_store_name: str = DEFAULT_ARTICLE_TEXT_NAME,
    force_rebuild: bool = False,
) -> ArticleTextStore:
    """Build or load one non-overlapping plain-text file per HTML article."""
    wiki_root = Path(wiki_dir) if wiki_dir else DEFAULT_WIKI_DIR
    if not wiki_root.is_dir():
        raise FileNotFoundError(f"Wikipedia corpus not found: {wiki_root}")

    html_paths = sorted(
        path
        for path in wiki_root.iterdir()
        if path.suffix.lower() == ".html" and not path.name.startswith("_")
    )
    source_files = [path.name for path in html_paths]
    store_root = article_text_store_path(text_store_name)
    manifest_path = store_root / "manifest.json"

    if manifest_path.is_file() and not force_rebuild:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        titles = manifest.get("titles", {})
        cache_matches = (
            manifest.get("extractor_version") == _ARTICLE_TEXT_EXTRACTOR_VERSION
            and manifest.get("source_files") == source_files
            and all((store_root / f"{source}.txt").is_file() for source in source_files)
        )
        if cache_matches:
            print(f"Loading extracted article text from {store_root}/")
            return ArticleTextStore(store_root, titles)

    print(f"Extracting {len(html_paths)} complete articles into {store_root}/")
    store_root.mkdir(parents=True, exist_ok=True)
    titles: dict[str, str] = {}
    for number, html_path in enumerate(html_paths, 1):
        raw = html_path.read_text(encoding="utf-8", errors="replace")
        title, body = extract_title_and_body(raw)
        title = title or html_path.stem.replace("_", " ")
        article_text = f"Article: {title}\nSource: {html_path.name}\n\n{body.strip()}\n"
        (store_root / f"{html_path.name}.txt").write_text(
            article_text, encoding="utf-8"
        )
        titles[html_path.name] = title
        if number % 250 == 0 or number == len(html_paths):
            print(f"  extracted {number}/{len(html_paths)}")

    manifest = {
        "extractor_version": _ARTICLE_TEXT_EXTRACTOR_VERSION,
        "source_directory": str(wiki_root.resolve()),
        "article_count": len(html_paths),
        "source_files": source_files,
        "titles": titles,
        "format": "one complete non-overlapping UTF-8 text file per HTML article",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return ArticleTextStore(store_root, titles)
