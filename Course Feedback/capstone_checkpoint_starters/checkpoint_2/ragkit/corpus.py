"""Reading the corpus into Documents and splitting them into passages. (Checkpoint 2)

    load_corpus()          the scenario's passages, from RAG_CORPUS_DIR (cached after the first load)
    load_wikipedia(folder) one Document per article section (references and links sections dropped)
    load_papers(folder)    one Document per PDF page
    load_emails(folder)    one Document per email
    chunk_documents(docs)  long Documents split into overlapping passages

Every Document keeps ``metadata["source"]``, the file it came from. In Checkpoint 3,
retrieval recall compares these sources with the source articles of each question.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from ragkit import config

DEFAULT_CHUNK_SIZE = 1500  # characters per passage
DEFAULT_OVERLAP = 150  # characters repeated between neighbouring passages


@dataclass
class Document:
    """A piece of the corpus: an article section, a PDF page, an email, or a passage of one."""

    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source(self) -> str:
        """The file this text came from, for example '100_metres.html'."""
        return self.metadata.get("source", self.id)


def normalize_source(name: str) -> str:
    """A file name or title in one comparable form.

    '100_metres.html', '100_metres.html.txt' and '100 metres' all become '100 metres'.
    """
    name = Path(str(name).strip()).name
    name = re.sub(r"(\.html?|\.pdf|\.txt)+$", "", name, flags=re.I)
    return " ".join(name.replace("_", " ").split()).lower()


# --- loading the scenario ---------------------------------------------------------

FILE_PATTERNS = {"wikipedia": "*.html", "papers": "*.pdf", "emails": "*.txt"}


def load_corpus(
    scenario: str | None = None,
    folder: Path | str | None = None,
    *,
    chunk_size: int | None = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
    limit: int | None = None,
    use_cache: bool = True,
) -> list[Document]:
    """The scenario's documents, split into passages (``chunk_size=None`` keeps them whole).

    ``limit`` reads only the first N files, to try things on a small corpus first.
    Reading thousands of files is slow, so the result is cached under
    RAG_WORK_DIR/cache/ and reused while the folder's files stay the same.
    """
    scenario = scenario or config.scenario()
    folder = Path(folder).expanduser() if folder else config.corpus_dir()
    files = sorted(folder.glob(FILE_PATTERNS[scenario]))[:limit]
    if not files:
        raise config.SetupError(f"No {FILE_PATTERNS[scenario]} files in {folder}.")

    cache_file = config.cache_dir() / f"{scenario}_{_fingerprint(files)}.jsonl"
    documents = _read_cache(cache_file) if use_cache else None
    if documents is None:
        loader = {"wikipedia": load_wikipedia, "papers": load_papers, "emails": load_emails}[scenario]
        print(f"Reading {len(files):,} {scenario} files from {folder} (cached after this run)...")
        documents = list(loader(files))
        if use_cache:
            with cache_file.open("w", encoding="utf-8") as handle:
                for document in documents:
                    # The default ASCII escaping keeps every record on one line, even when the
                    # text holds Unicode line separators (common in PDF text).
                    handle.write(json.dumps(asdict(document)) + "\n")
    if chunk_size:
        documents = chunk_documents(documents, chunk_size, overlap)
    return documents


def _read_cache(cache_file: Path) -> list[Document] | None:
    """The cached documents, or None when there is no usable cache (then the corpus is re-read)."""
    if not cache_file.is_file():
        return None
    try:
        with cache_file.open(encoding="utf-8") as handle:
            return [Document(**json.loads(line)) for line in handle if line.strip()]
    except (json.JSONDecodeError, TypeError):
        print(f"The corpus cache {cache_file.name} is unreadable; reading the corpus again.")
        return None


def _fingerprint(files: list[Path]) -> str:
    """Changes whenever a file is added, removed, or edited."""
    digest = hashlib.sha1()
    for path in files:
        stat = path.stat()
        digest.update(f"{path.resolve()}|{stat.st_size}|{int(stat.st_mtime)}".encode())
    return digest.hexdigest()[:12]


def chunk_documents(
    documents: Iterable[Document], size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP
) -> list[Document]:
    """Split long documents into passages of about ``size`` characters.

    Each passage starts with a line naming its title and section, so a passage about
    "the final" still matches a question about the 100 metres.
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)
    passages: list[Document] = []
    for document in documents:
        pieces = splitter.split_text(document.text) if len(document.text) > size else [document.text]
        title = document.metadata.get("title", "")
        section = document.metadata.get("section", "")
        header = " > ".join(part for part in (title, section) if part)
        for number, piece in enumerate(pieces, start=1):
            passage_id = document.id if len(pieces) == 1 else f"{document.id}-{number}"
            text = f"{header}\n{piece}" if header else piece
            passages.append(Document(passage_id, text, {**document.metadata, "part": number, "parts": len(pieces)}))
    return passages


# --- Wikipedia ----------------------------------------------------------------------

# Page furniture that is not article content: edit links, citation markers, navigation
# boxes, tables of contents, reference lists, maintenance banners, image captions.
_STRIP = (
    ".mw-editsection", "sup.reference", "style", "script", "link", '[role="navigation"]',
    ".navbox", ".vertical-navbox", ".sistersitebox", ".sidebar", ".mw-table-of-contents-container",
    "#toc", ".toc", "ol.references", ".reflist", ".refbegin", ".mw-references-wrap", ".ambox",
    ".mbox", ".ombox", ".tmbox", ".metadata", ".noprint", ".mw-empty-elt", ".mw-jump-link",
    "#coordinates", ".hatnote", "figure", ".thumb",
)
# Sections that list references or links rather than say anything about the subject.
_SKIP_SECTIONS = {
    "references", "external links", "see also", "notes", "further reading", "sources",
    "bibliography", "citations", "footnotes", "notes and references", "works cited",
}
_BLOCK_TAGS = {"p", "ul", "ol", "dl", "table", "blockquote", "pre", "div"}


def load_wikipedia(files: Iterable[Path]) -> Iterator[Document]:
    files = list(files)
    in_corpus = {path.name for path in files}
    for path in files:
        yield from _wikipedia_sections(path, in_corpus)


def _wikipedia_sections(path: Path, in_corpus: set[str]) -> Iterator[Document]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="ignore"), "lxml")
    title_tag = soup.select_one(".mw-page-title-main")
    if title_tag:
        title = title_tag.get_text(" ", strip=True)
    elif soup.title:
        title = soup.title.get_text().replace(" - Wikipedia", "").strip()
    else:
        title = path.stem.replace("_", " ")
    roots = soup.select("div.mw-parser-output")
    if not roots:
        return
    root = max(roots, key=lambda tag: len(tag.get_text()))
    for junk in root.select(", ".join(_STRIP)):
        junk.decompose()

    # The infobox (the summary table at the top right) becomes the first lines of the lead.
    # A header row ("World records") gives context to the rows under it ("Men: ...").
    lead: list[str] = []
    infobox = root.select_one("table.infobox")
    if infobox is not None:
        header = ""
        for row in infobox.find_all("tr"):
            label, value = row.find("th"), row.find("td")
            if label is not None and value is None:
                header = _clean(label.get_text(" "))
            elif label is not None and value is not None:
                prefix = f"{header}, " if header else ""
                lead.append(f"{prefix}{_clean(label.get_text(' '))}: {_clean(value.get_text(' '))}")
            elif value is not None and "infobox-image" not in (value.get("class") or []):
                text = _clean(value.get_text(" "))
                if text:
                    lead.append(text)
        infobox.decompose()

    sections: list[tuple[list[str], list[str], set[str]]] = [([], lead, set())]
    path_titles: list[str] = []
    skipping = False
    for element in root.find_all(recursive=False):
        level, heading = _heading(element)
        if heading is not None:
            if level == 2:
                skipping = heading.lower() in _SKIP_SECTIONS
            path_titles = path_titles[: level - 2] + [heading]
            if not skipping:
                sections.append((list(path_titles), [], set()))
            continue
        if skipping:
            continue
        text = _element_text(element)
        if text:
            sections[-1][1].append(text)
            sections[-1][2].update(_local_links(element, in_corpus))

    for number, (titles, lines, links) in enumerate(sections):
        text = "\n".join(lines).strip()
        if not text:
            continue
        yield Document(
            id=f"{path.name}#{number}",
            text=text,
            metadata={
                "source": path.name,
                "title": title,
                "section": " > ".join(titles) or "Introduction",
                "links": sorted(links),
            },
        )


def _heading(element: Any) -> tuple[int, str | None]:
    """(level, title) when ``element`` is a section heading, else (0, None)."""
    tag = element
    if element.name == "div" and "mw-heading" in (element.get("class") or []):
        tag = element.find(re.compile(r"^h[2-6]$"))
    if tag is not None and re.fullmatch(r"h[2-6]", tag.name or ""):
        return int(tag.name[1]), _clean(tag.get_text(" "))
    return 0, None


def _element_text(element: Any) -> str:
    """Readable text for one block: list items on their own lines, table rows as 'a | b | c'."""
    name = element.name
    if name == "table":
        rows = []
        for row in element.find_all("tr"):
            cells = [_clean(cell.get_text(" ")) for cell in row.find_all(["th", "td"])]
            if any(cells):
                rows.append(" | ".join(cells))
        caption = element.find("caption")
        if caption:
            rows.insert(0, f"Table: {_clean(caption.get_text(' '))}")
        return "\n".join(rows)
    if name in {"ul", "ol"}:
        items = [_clean(item.get_text(" ")) for item in element.find_all("li", recursive=False)]
        return "\n".join(f"- {item}" for item in items if item)
    if name == "div" and element.find(_BLOCK_TAGS - {"div"}):
        parts = [_element_text(child) for child in element.find_all(recursive=False)]
        return "\n".join(part for part in parts if part)
    return _clean(element.get_text(" "))


def _local_links(element: Any, in_corpus: set[str]) -> set[str]:
    """Files in the corpus that this block links to (used for the graph in Checkpoint 4)."""
    found = set()
    for anchor in element.find_all("a", href=True):
        href = anchor["href"]
        if href.startswith("/wiki/") and ":" not in href[6:].split("#")[0]:
            target = unquote(href[6:].split("#")[0]) + ".html"
            if target in in_corpus:
                found.add(target)
    return found


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text.replace("​", "")).strip()
    return re.sub(r"\s+([,.;:!?)])", r"\1", text).replace("( ", "(")


# --- research papers ----------------------------------------------------------------

def load_papers(files: Iterable[Path]) -> Iterator[Document]:
    from pypdf import PdfReader

    logging.getLogger("pypdf").setLevel(logging.ERROR)  # font warnings are noise here

    for path in files:
        try:
            reader = PdfReader(path)
        except Exception as error:  # a damaged PDF should not stop the whole corpus
            print(f"  skipped {path.name}: {type(error).__name__}")
            continue
        pages = [(page.extract_text() or "") for page in reader.pages]
        title = _paper_title(reader, pages, path)
        for number, text in enumerate(pages, start=1):
            text = re.sub(r"[ \t]+", " ", text).strip()
            if text:
                yield Document(
                    id=f"{path.name}#p{number}",
                    text=text,
                    metadata={"source": path.name, "title": title, "section": f"page {number}", "page": number},
                )


# First-page lines that are running headers, not titles.
_HEADER_LINE = re.compile(r"proceedings|findings of|pages\s+\d|\bvol\.|volume\s+\d|copyright|©|arxiv|doi\.org", re.I)


def _paper_title(reader: Any, pages: list[str], path: Path) -> str:
    """The PDF's own title when it has a real one, else the first line that is not a header."""
    title = getattr(reader.metadata, "title", None) if reader.metadata else None
    if title and len(title.strip()) > 8 and not title.lower().endswith((".dvi", ".pdf", ".doc", ".tex")):
        return re.sub(r"^LNCS\s+\d+\s*-\s*", "", title.strip())
    for line in (pages[0] if pages else "").splitlines():
        line = line.strip()
        if len(line) > 8 and not _HEADER_LINE.search(line):
            return line[:200]
    return path.stem


# --- emails (the lab corpus) ----------------------------------------------------------

def load_emails(files: Iterable[Path]) -> Iterator[Document]:
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore").strip()
        headers = dict(re.findall(r"^(Subject|From|To|Date):\s*(.*)$", text, re.M))
        yield Document(
            id=path.name,
            text=text,
            metadata={
                "source": path.name,
                "title": headers.get("Subject", path.stem),
                "section": "",
                "from": headers.get("From", ""),
                "to": headers.get("To", ""),
                "date": headers.get("Date", ""),
            },
        )
