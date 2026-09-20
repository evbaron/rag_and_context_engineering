"""Load Wikipedia HTML articles into text chunks for BM25 / vector / hybrid retrieval."""
from __future__ import annotations

import html as html_lib
import json
import re
import urllib.parse
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WIKI_DIR = ENGINE_ROOT / "Wikipedia Library"
DEFAULT_CHROMA_DB_ROOT = Path(__file__).resolve().parent / "db"
DEFAULT_CHROMA_DB_NAME = "wikipedia"
DEFAULT_CHROMA_DIR = DEFAULT_CHROMA_DB_ROOT / DEFAULT_CHROMA_DB_NAME
DEFAULT_SECTION_CHROMA_DB_NAME = "wikipedia_sections_max10000_no_overlap"
DEFAULT_SECTION_MAX_CHARS = 10000
DEFAULT_SECTION_OVERLAP = 0
DEFAULT_ARTICLE_TEXT_ROOT = Path(__file__).resolve().parent / "db" / "article_text"
DEFAULT_ARTICLE_TEXT_NAME = "wikipedia_plain_text"
DEFAULT_MARKDOWN_STORE_NAME = "wikipedia_markdown"

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


# ─── Markdown + structured sidecar extraction (BeautifulSoup) ────────
# HTML -> (readable Markdown, structured JSON sidecar). The markdown preserves
# sections, the infobox, tables, blockquotes, captions and inline links; the
# sidecar carries the fields the knowledge graph needs — categories, tables, and
# links split into local / wiki / external. bs4 + markdownify are imported lazily
# so the plain-text paths above keep working without those packages installed.
#     pip install beautifulsoup4 markdownify lxml
# v2: strip navigation templates by [role="navigation"] + .sidebar. v1 missed
# sidebar/role-based nav, which leaked into the markdown and polluted sidecar links.
_MARKDOWN_EXTRACTOR_VERSION = 2

# /wiki/<Prefix>:... namespaces that are never article links.
_WIKI_NAMESPACES = {
    "category", "file", "image", "help", "wikipedia", "template", "special",
    "portal", "talk", "user", "user talk", "mediawiki", "module", "draft", "book",
    "s", "wikt", "commons",
}

# Chrome removed from the prose BEFORE links or markdown are read off the tree, so
# navigation/citation/maintenance links never pollute the graph. Grouped so any
# line can be commented back in.
_MD_STRIP_SELECTORS = (
    ".mw-editsection", "sup.reference", "style", "link",            # edit links, [1] refs
    '[role="navigation"]',                                          # every nav template (robust)
    ".navbox", ".vertical-navbox", ".sistersitebox", ".navbox-styles", ".sidebar",  # nav/sidebars
    ".mw-table-of-contents-container", "#toc", ".toc",             # table of contents
    "ol.references", ".reflist", ".refbegin", ".mw-references-wrap",  # citation dump
    ".ambox", ".mbox", ".ombox", ".tmbox", ".dmbox", ".metadata",  # maintenance banners
    ".noprint", ".mw-empty-elt", ".mw-jump-link", "#coordinates",
)

_ZERO_WIDTH = dict.fromkeys(map(ord, "﻿​‎‏"), None)


def _md_clean_text(text: str) -> str:
    text = text.translate(_ZERO_WIDTH)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.;:])", r"\1", text)  # "Soho , London" -> "Soho, London"


def _classify_wiki_href(href: str, corpus_files: set[str]) -> dict | None:
    """Classify an <a href> as a local / wiki / external article link (or None).

    local    -> /wiki/<Target> whose <Target>.html is in the corpus (referenceable now)
    wiki      -> /wiki/<Target> not in the corpus (real article, pullable later via url)
    external -> off-wiki http(s) link (citation / official site)
    """
    if not href or href.startswith("#"):
        return None

    def _is_article(target: str) -> bool:
        prefix = target.split(":", 1)[0].lower() if ":" in target else ""
        return bool(target) and prefix not in _WIKI_NAMESPACES

    if href.startswith("/wiki/"):
        raw_target = href[len("/wiki/"):]
        target = urllib.parse.unquote(raw_target.split("#", 1)[0])
        if not _is_article(target):
            return None
        url = f"https://en.wikipedia.org/wiki/{raw_target}"
        fname = f"{target}.html"
        if fname in corpus_files:
            return {"scope": "local", "target": target, "source_file": fname, "url": url}
        return {"scope": "wiki", "target": target, "url": url}

    if href.startswith(("http://", "https://", "//")):
        url = "https:" + href if href.startswith("//") else href
        host = urllib.parse.urlparse(url).netloc.lower()
        if host.endswith("wikipedia.org") and "/wiki/" in url:
            target = urllib.parse.unquote(url.split("/wiki/", 1)[1]).split("#", 1)[0]
            if _is_article(target):
                fname = f"{target}.html"
                scope = "local" if fname in corpus_files else "wiki"
                rec = {"scope": scope, "target": target, "url": url}
                if scope == "local":
                    rec["source_file"] = fname
                return rec
        return {"scope": "external", "url": url}

    return None  # /w/index.php edit links, relative ./ , mailto:, etc.


def _collect_links(container, corpus_files: set[str], region: str, sink: dict) -> None:
    """Aggregate <a> links in `container` into `sink`, keyed by (scope, target|url)."""
    for anchor_el in container.find_all("a", href=True):
        info = _classify_wiki_href(anchor_el["href"], corpus_files)
        if not info:
            continue
        text = _md_clean_text(anchor_el.get_text(" ", strip=True))
        key = (info["scope"], info.get("target") or info["url"])
        rec = sink.get(key)
        if rec is None:
            rec = {**info, "anchors": [], "count": 0, "regions": set()}
            sink[key] = rec
        rec["count"] += 1
        rec["regions"].add(region)
        if text and text not in rec["anchors"]:
            rec["anchors"].append(text)


def _content_root(soup):
    """The article body = the largest .mw-parser-output (skips the tiny page-
    indicator wrapper that shares the class). None if the page has no content."""
    candidates = soup.select("div.mw-parser-output")
    return max(candidates, key=lambda p: len(p.get_text())) if candidates else None


def _md_extract_title(soup, fallback: str) -> str:
    el = soup.select_one(".mw-page-title-main")
    if el:
        return _md_clean_text(el.get_text(" ", strip=True))
    if soup.title:
        return soup.title.get_text().replace(" - Wikipedia", "").strip()
    return fallback


def _extract_categories(soup) -> list[str]:
    box = soup.select_one("#mw-normal-catlinks")
    if not box:
        return []
    return [
        urllib.parse.unquote(a["href"].split("/wiki/Category:", 1)[1]).replace("_", " ")
        for a in box.select('a[href*="/wiki/Category:"]')
    ]


def _extract_sections(root) -> list[dict]:
    sections = []
    for heading in root.find_all(["h2", "h3", "h4", "h5", "h6"]):
        title = _md_clean_text(heading.get_text(" ", strip=True).replace("[edit]", ""))
        if title and title.lower() != "contents":
            sections.append(
                {"level": int(heading.name[1]), "id": heading.get("id") or "", "title": title}
            )
    return sections


def _extract_infobox(root, corpus_files: set[str], sink: dict) -> dict | None:
    """Pull the infobox as key->value fields, collect its links, then remove it
    from the prose tree so it is not rendered a second time as a mangled table."""
    infobox = root.select_one("table.infobox")
    if not infobox:
        return None
    _collect_links(infobox, corpus_files, "infobox", sink)
    title_el = infobox.select_one(".infobox-title, caption")
    fields: dict[str, str] = {}
    for row in infobox.find_all("tr"):
        th, td = row.find("th"), row.find("td")
        if th and td:
            label = _md_clean_text(th.get_text(" ", strip=True))
            value = _md_clean_text(td.get_text(" ", strip=True))
            if label and value and label not in fields:
                fields[label] = value
    infobox.decompose()
    return {
        "title": _md_clean_text(title_el.get_text(" ", strip=True)) if title_el else "",
        "fields": fields,
    }


def _extract_tables(root, corpus_files: set[str], sink: dict) -> list[dict]:
    """Capture data tables (table.wikitable) as header + rows for future
    table->relationship extraction. The tables stay in the tree for markdown."""
    tables = []
    for table in root.select("table.wikitable"):
        _collect_links(table, corpus_files, "table", sink)
        caption = table.find("caption")
        rows = table.find_all("tr")
        headers = (
            [_md_clean_text(c.get_text(" ", strip=True)) for c in rows[0].find_all(["th", "td"])]
            if rows else []
        )
        body = []
        for row in rows[1:]:
            cells = [_md_clean_text(c.get_text(" ", strip=True)) for c in row.find_all(["th", "td"])]
            if any(cells):
                body.append(cells)
        tables.append(
            {
                "caption": _md_clean_text(caption.get_text(" ", strip=True)) if caption else None,
                "headers": headers,
                "rows": body,
                "n_rows": len(body),
            }
        )
    return tables


def _prepare_prose(root) -> None:
    """Strip chrome and normalize <a> tags IN PLACE, before links/markdown are read."""
    junk = root.select(", ".join(_MD_STRIP_SELECTORS))
    for element in junk:
        element.decompose()
    for anchor_el in root.find_all("a", href=True):
        href = anchor_el["href"]
        if href.startswith("/w/") or "redlink=1" in href:  # non-existent page -> plain text
            anchor_el.unwrap()
        else:
            anchor_el.attrs.pop("title", None)  # redundant title="..." adds markdown noise


_WIKI_MD_CONVERTER = None


def _get_md_converter():
    """A cached markdownify converter tuned for these pages (ATX headings, dash
    bullets, images dropped). Imported lazily so bs4/markdownify stay optional."""
    global _WIKI_MD_CONVERTER
    if _WIKI_MD_CONVERTER is None:
        from markdownify import MarkdownConverter

        class _WikiMarkdown(MarkdownConverter):
            def convert_img(self, *args, **kwargs):  # drop images; captions survive as text
                return ""

        _WIKI_MD_CONVERTER = _WikiMarkdown(heading_style="ATX", bullets="-")
    return _WIKI_MD_CONVERTER


def _to_markdown(root) -> str:
    """Convert a prepared prose tree to markdown. Assumes _prepare_prose ran."""
    markdown = _get_md_converter().convert_soup(root)
    markdown = markdown.translate(_ZERO_WIDTH)
    markdown = re.sub(r"\[edit\]", "", markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)   # collapse blank runs
    markdown = re.sub(r"[ \t]+\n", "\n", markdown)   # trailing spaces
    return markdown.strip()


def _render_markdown(title: str, infobox: dict | None, body_md: str) -> str:
    parts = [f"# {title}\n"]
    if infobox and infobox["fields"]:
        parts.append("## Infobox\n")
        if infobox.get("title"):
            parts.append(f"**{infobox['title']}**\n")
        parts.extend(f"- **{label}:** {value}" for label, value in infobox["fields"].items())
        parts.append("")
    parts.append(body_md)
    return "\n".join(parts).strip() + "\n"


def _finalize_links(sink: dict) -> dict:
    buckets: dict[str, list] = {"local": [], "wiki": [], "external": []}
    for rec in sink.values():
        rec = dict(rec)
        rec["regions"] = sorted(rec["regions"])
        buckets[rec.pop("scope")].append(rec)
    for items in buckets.values():
        items.sort(key=lambda r: r["count"], reverse=True)
    return buckets


def _empty_sidecar(source: str, title: str) -> dict:
    wiki_title = source[:-5] if source.endswith(".html") else source
    return {
        "source": source, "title": title, "wiki_title": wiki_title,
        "categories": [], "sections": [], "infobox": None, "tables": [],
        "links": {"local": [], "wiki": [], "external": []},
        "stats": {"n_categories": 0, "n_sections": 0, "n_tables": 0,
                  "n_local": 0, "n_wiki": 0, "n_external": 0, "md_chars": 0},
    }


def extract_markdown_article(raw: str, source: str, corpus_files: set[str]) -> tuple[str, dict]:
    """Extract one HTML article into (markdown, sidecar dict).

    `source` is the HTML filename (e.g. 'John_Snow.html'); `corpus_files` is the
    set of HTML filenames in the corpus, used to split links into local vs wiki.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(raw, "lxml")
    wiki_title = source[:-5] if source.endswith(".html") else source
    title = _md_extract_title(soup, wiki_title.replace("_", " "))
    root = _content_root(soup)
    if root is None:
        return f"# {title}\n", _empty_sidecar(source, title)

    categories = _extract_categories(soup)
    sections = _extract_sections(root)
    sink: dict = {}
    infobox = _extract_infobox(root, corpus_files, sink)   # collect infobox links, then drop it
    tables = _extract_tables(root, corpus_files, sink)     # collect table links (tables kept)
    _prepare_prose(root)                                   # strip chrome BEFORE body-link scan
    _collect_links(root, corpus_files, "body", sink)       # now: real prose + see-also links
    links = _finalize_links(sink)

    markdown = _render_markdown(title, infobox, _to_markdown(root))
    sidecar = {
        "source": source,
        "title": title,
        "wiki_title": wiki_title,
        "categories": categories,
        "sections": sections,
        "infobox": infobox,
        "tables": tables,
        "links": links,
        "stats": {
            "n_categories": len(categories), "n_sections": len(sections),
            "n_tables": len(tables), "n_local": len(links["local"]),
            "n_wiki": len(links["wiki"]), "n_external": len(links["external"]),
            "md_chars": len(markdown),
        },
    }
    return markdown, sidecar


@dataclass(frozen=True)
class MarkdownArticle:
    """One extracted article: readable markdown plus its structured sidecar."""

    source: str
    title: str
    markdown: str
    metadata: dict
    markdown_path: Path
    sidecar_path: Path

    @property
    def text(self) -> str:
        """Body text for context assembly. Aliases ``markdown`` so a MarkdownArticle
        can stand in wherever an ArticleText is expected (e.g.
        ``format_full_articles_context``), letting the LLM-context source switch
        between the plain-text and markdown stores with no other code changes."""
        return self.markdown


class MarkdownArticleStore:
    """Lazy access to the <source>.md + <source>.json pair per article."""

    def __init__(self, root: Path, titles: dict[str, str]) -> None:
        self.root = root
        self._titles = titles

    def __len__(self) -> int:
        return len(self._titles)

    def has_article(self, source: str) -> bool:
        return source in self._titles

    def sources(self) -> list[str]:
        return list(self._titles)

    def markdown_path(self, source: str) -> Path:
        return self.root / f"{source}.md"

    def sidecar_path(self, source: str) -> Path:
        return self.root / f"{source}.json"

    def load(self, source: str) -> MarkdownArticle:
        if source not in self._titles:
            raise KeyError(f"Markdown article is not available: {source}")
        md_path, json_path = self.markdown_path(source), self.sidecar_path(source)
        return MarkdownArticle(
            source=source,
            title=self._titles[source],
            markdown=md_path.read_text(encoding="utf-8"),
            metadata=json.loads(json_path.read_text(encoding="utf-8")),
            markdown_path=md_path,
            sidecar_path=json_path,
        )

    def load_metadata(self, source: str) -> dict:
        return json.loads(self.sidecar_path(source).read_text(encoding="utf-8"))

    def iter_metadata(self):
        """Yield (source, sidecar dict) for every article — the graph builder's input."""
        for source in self._titles:
            yield source, self.load_metadata(source)


def build_or_load_markdown_store(
    wiki_dir: str | Path | None = None,
    *,
    store_name: str = DEFAULT_MARKDOWN_STORE_NAME,
    force_rebuild: bool = False,
) -> MarkdownArticleStore:
    """Build or load one <source>.md + <source>.json pair per HTML article.

    Mirrors build_or_load_article_text_store: cached via a manifest, rebuilt when
    the extractor version or the set of source files changes.
    """
    wiki_root = Path(wiki_dir) if wiki_dir else DEFAULT_WIKI_DIR
    if not wiki_root.is_dir():
        raise FileNotFoundError(f"Wikipedia corpus not found: {wiki_root}")

    html_paths = sorted(
        path
        for path in wiki_root.iterdir()
        if path.suffix.lower() == ".html" and not path.name.startswith("_")
    )
    source_files = [path.name for path in html_paths]
    store_root = article_text_store_path(store_name)
    manifest_path = store_root / "manifest.json"

    if manifest_path.is_file() and not force_rebuild:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        titles = manifest.get("titles", {})
        cache_matches = (
            manifest.get("extractor_version") == _MARKDOWN_EXTRACTOR_VERSION
            and manifest.get("source_files") == source_files
            and all(
                (store_root / f"{source}.md").is_file()
                and (store_root / f"{source}.json").is_file()
                for source in source_files
            )
        )
        if cache_matches:
            print(f"Loading extracted markdown from {store_root}/")
            return MarkdownArticleStore(store_root, titles)

    print(f"Extracting {len(html_paths)} articles to markdown + JSON in {store_root}/")
    store_root.mkdir(parents=True, exist_ok=True)
    corpus_files = set(source_files)
    titles: dict[str, str] = {}
    failures: list[tuple[str, str]] = []
    for number, html_path in enumerate(html_paths, 1):
        raw = html_path.read_text(encoding="utf-8", errors="replace")
        try:
            markdown, sidecar = extract_markdown_article(raw, html_path.name, corpus_files)
        except Exception as exc:  # never lose an article to one bad page
            fallback_title = html_path.stem.replace("_", " ")
            markdown, sidecar = f"# {fallback_title}\n", _empty_sidecar(html_path.name, fallback_title)
            failures.append((html_path.name, repr(exc)))
        (store_root / f"{html_path.name}.md").write_text(markdown, encoding="utf-8")
        (store_root / f"{html_path.name}.json").write_text(
            json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        titles[html_path.name] = sidecar["title"]
        if number % 250 == 0 or number == len(html_paths):
            print(f"  extracted {number}/{len(html_paths)}")

    manifest = {
        "extractor_version": _MARKDOWN_EXTRACTOR_VERSION,
        "source_directory": str(wiki_root.resolve()),
        "article_count": len(html_paths),
        "source_files": source_files,
        "titles": titles,
        "failures": failures,
        "format": "one <source>.md (readable) + <source>.json (structured sidecar) per HTML article",
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if failures:
        print(f"  NOTE: {len(failures)} article(s) fell back to minimal extraction "
              f"(recorded in manifest 'failures').")
    return MarkdownArticleStore(store_root, titles)


if __name__ == "__main__":
    import argparse

    arg_parser = argparse.ArgumentParser(
        description="Build the Wikipedia markdown + JSON sidecar store."
    )
    arg_parser.add_argument("wiki_dir", nargs="?", default=None, help="Wikipedia HTML dir")
    arg_parser.add_argument("--force", action="store_true", help="rebuild even if cached")
    cli_args = arg_parser.parse_args()
    md_store = build_or_load_markdown_store(cli_args.wiki_dir, force_rebuild=cli_args.force)
    print(f"Store ready: {len(md_store)} articles at {md_store.root}")
