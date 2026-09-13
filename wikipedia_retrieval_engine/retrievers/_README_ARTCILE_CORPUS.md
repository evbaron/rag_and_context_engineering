# Wikipedia article corpus and preprocessing

This document explains how the original Wikipedia HTML files become the different
corpus representations used by the retrieval experiments.

The source corpus contains approximately 2,417 Wikipedia HTML files:

```text
wikipedia_retrieval_engine/Wikipedia/
```

The preprocessing code is primarily in `retrievers/corpus.py`. Vector persistence is
implemented in `retrievers/vector.py`, and full-article selection is implemented in
`retrievers/expansion.py`.

## The four corpus representations

The project intentionally keeps four distinct representations because they answer
different experimental questions. The first three flatten the HTML to plain text with
the standard-library parser; the fourth preserves formatting and relationships for
structure-aware and graph-augmented retrieval.

### Character-window chunks

Used by the original baseline retrievers.

```text
HTML article
→ extracted plain article body
→ 1,600-character chunks
→ 200-character overlap
```

These chunks support:

- BM25 keyword retrieval
- Chroma vector retrieval
- hybrid BM25/vector retrieval

The matching Chroma index is normally:

```text
retrievers/db/wikipedia_chars1600_overlap200/
```

### Article-section chunks

Used by the article-header experiment.

```text
HTML article
→ h2–h6 heading hierarchy
→ one natural chunk per section
→ split only when a section exceeds 10,000 characters
→ zero overlap between fallback pieces
```

The matching Chroma index is:

```text
retrievers/db/wikipedia_sections_max10000_no_overlap/
```

### Complete article text files

Used after retrieval in the full-article context experiment.

```text
HTML article
→ one continuous plain-text extraction
→ one UTF-8 .txt file
```

These files are stored under:

```text
retrievers/db/article_text/wikipedia_plain_text/
```

They are not a vector database. They are a persistent file collection used to load a
complete selected article without reconstructing it from overlapping chunks.

### Markdown + structured sidecar

Used for structure-aware retrieval and as the input to the knowledge graph.

```text
HTML article
→ BeautifulSoup DOM (main article body only)
→ readable Markdown  (sections, infobox, tables, inline links)  → one .md file
→ structured sidecar (categories, links, tables, sections)      → one .json file
```

Unlike the three representations above, this pipeline preserves formatting and extracts
the per-article relationships (links, shared categories) that graph-augmented retrieval
needs. The files are stored under:

```text
retrievers/db/article_text/wikipedia_markdown/
```

This representation is documented in detail in
[Markdown + structured sidecar collection](#markdown--structured-sidecar-collection).

---

## Shared HTML preprocessing

This section describes the three plain-text representations. All three begin with
`extract_title_and_body(raw)`, built on the standard-library `html.parser`. The
Markdown representation uses a separate BeautifulSoup pipeline and is documented under
[Markdown + structured sidecar collection](#markdown--structured-sidecar-collection).

Both character chunking and complete article extraction begin with
`extract_title_and_body(raw)`.

### 1. Read the HTML safely

Each source file is read as UTF-8:

```python
raw = path.read_text(encoding="utf-8", errors="replace")
```

Invalid byte sequences are replaced instead of causing the entire preprocessing run to
fail.

### 2. Extract the article title

The extractor first looks for Wikipedia's primary page-title element:

```html
<span class="mw-page-title-main">...</span>
```

If that element is unavailable, it falls back to the HTML `<title>` element and removes
the trailing ` - Wikipedia` text.

If neither title is available, the loader derives a readable title from the source
filename.

### 3. Isolate the main article body

`_article_body_markup()` locates the HTML element whose ID is `mw-content-text`.

Content outside that element is not treated as article body text. This avoids much of
the surrounding Wikipedia page navigation and interface.

### 4. Stop before reference/footer material

The body is cut before the earliest available marker for:

- References
- Notes
- the printable-page footer

Therefore, “complete article text” in this project means the complete extracted main
article body before References/Notes. It does not mean every byte from the original
HTML file.

### 5. Ignore non-content elements

The HTML parsers ignore text inside:

- `script`
- `style`
- `noscript`
- `svg`

This prevents JavaScript, CSS, fallback markup, and SVG labels from entering retrieval
text.

### 6. Convert HTML structure into readable text

Paragraphs, divisions, list items, table rows, headings, definition-list items, and
line breaks produce text boundaries.

HTML entities are converted automatically. For example, `&amp;` becomes `&`.

### 7. Normalize text

The extractors:

- remove Wikipedia `[edit]` labels;
- collapse repeated spaces and tabs;
- remove spaces around line breaks;
- reduce three or more consecutive newlines to two;
- remove leading and trailing whitespace.

The resulting text preserves useful paragraph/list boundaries while removing most HTML
presentation noise.

---

## Character-window chunking in detail

`load_wikipedia_chunks()` creates the baseline `WikiChunk` objects.

### Default configuration

```python
CHUNK_SIZE = 1600
CHUNK_OVERLAP = 200
```

### Boundary selection

For each chunk, the algorithm initially considers a 1,600-character window. If the
window does not reach the end of the article, it looks backward for a better natural
break:

1. paragraph boundary (`\n\n`);
2. sentence boundary (`. `);
3. line boundary (`\n`).

A natural break is used only when it occurs after at least one-third of the requested
chunk size. This avoids producing an extremely short chunk merely because an early
newline exists.

### Overlap

After producing a chunk, the next chunk starts 200 characters before the previous one
ended.

The overlap helps preserve meaning around an arbitrary boundary. Its cost is duplicate
text across adjacent chunks. This duplication is acceptable for baseline retrieval but
is not used to construct complete-article context.

### Chunk IDs

Character chunks have IDs such as:

```text
1580.html#0
1580.html#1
1580.html#2
```

Each `WikiChunk` stores:

- `doc_id`
- source HTML filename
- article title
- chunk text
- chunk position within the article

---

## Article-section chunking in detail

`load_wikipedia_section_chunks()` uses `_HTMLSectionExtractor` to preserve the HTML
heading hierarchy.

### Heading hierarchy

Wikipedia headings are interpreted as follows:

```text
h2 → top-level article section
h3 → child of the current h2
h4 → child of the current h3
h5 → child of the current h4
h6 → child of the current h5
```

For example:

```text
Events
Events > January–March
Events > April–June
Events > July–September
```

### What the parent section contains

The parent `Events` chunk contains only text directly below the `Events` heading and
before the first child heading.

It does not automatically contain the text from `Events > January–March` or the other
child sections. This prevents parent/child text duplication.

### Parser sequence

1. Text before the first `h2`–`h6` heading is assigned to `Lead`.
2. When a heading begins, accumulated body text for the previous section is finalized.
3. The heading level updates the active hierarchy path.
4. Text is collected under that exact path until the next heading begins.
5. Empty sections are not emitted.
6. The article title and complete section path are prepended to the indexed text.

An indexed section therefore begins like:

```text
Article: 1580
Section: Events > April–June

April 6 – The Dover Straits earthquake occurs...
```

Including these labels helps both keyword and semantic retrieval understand the article
and section identity.

### Oversized sections

The current experiment uses:

```python
MAX_SECTION_CHARS = 10000
SECTION_OVERLAP = 0
```

A section at or below 10,000 characters remains one natural chunk. A larger section is
split using the same paragraph/sentence/line boundary logic as character chunking, but
with zero overlap.

The actual body allowance is slightly less than 10,000 characters because the
`Article:` and `Section:` prefix is included in the maximum chunk size.

### Section IDs and metadata

Section chunk IDs look like:

```text
1580.html#section-003-00
```

The first number identifies the natural section in article order. The second identifies
a fallback piece when an oversized section must be split.

Each section chunk additionally stores:

- `section_title`, such as `April–June`;
- `section_path`, such as `Events > April–June`.

Chroma stores these fields as document metadata.

### Important retrieval implication

Retrieving the parent `Events` section does not automatically retrieve all child
sections. A broad question may still require several child sections or a later
parent-to-children expansion strategy.

Section chunking improves natural boundaries; it does not by itself guarantee complete
coverage of a broad article-level question.

---

## Chroma vector databases

Chroma persists text chunks, metadata, and embedding vectors.

### What is stored

Each Chroma document contains:

- indexed chunk text;
- source chunk ID;
- article filename;
- article title;
- section title/path when section chunking is used;
- the embedding vector generated from the chunk text.

### Character-chunk Chroma index

```text
retrievers/db/wikipedia_chars1600_overlap200/
```

This index must be used only with the baseline 1,600/200 character corpus.

### Section-chunk Chroma index

```text
retrievers/db/wikipedia_sections_max10000_no_overlap/
```

This index must be built from the section corpus. It cannot reuse vectors from the
character-chunk corpus because the indexed text and IDs are different.

### Build versus load

`build_or_load_db()` checks the named directory:

- if it contains a database, Chroma loads it;
- otherwise, all supplied chunks are embedded and persisted there.

Loading avoids re-embedding the article corpus after Python restarts. Every new search
still requires embedding the query.

### Current compatibility limitation

The Chroma loader currently treats a nonempty named directory as reusable. It does not
yet validate a detailed corpus/index manifest.

Database names must therefore accurately identify preprocessing. If chunking rules,
the embedding model, source corpus, or extraction logic change, use a new database name
or intentionally rebuild the corresponding directory.

---

## BM25 indexes

BM25 uses the same `WikiChunk` list as vector retrieval, but it is not persisted as a
database.

When a `Bm25Retriever` is created:

1. every corpus chunk is tokenized;
2. stopwords are removed;
3. `BM25Okapi` builds its term-frequency and document-length structures in memory.

The document corpus is tokenized once per retriever construction, not once per query.
Each query is tokenized when searched.

After Python exits, the BM25 index disappears and is rebuilt on the next run. This uses
local CPU only and does not consume embedding credits.

---

## Complete article plain-text collection

`build_or_load_article_text_store()` maintains the full extracted article collection.

### Directory structure

```text
retrievers/db/article_text/wikipedia_plain_text/
  manifest.json
  100_metres.html.txt
  1580.html.txt
  1972_Winter_Olympics.html.txt
  ...
```

The current collection contains 2,417 article text files plus the manifest and uses
approximately 75 MB.

### File format

Each file begins with:

```text
Article: 1580
Source: 1580.html

<complete extracted main article body>
```

The text is created directly from the HTML body extraction. It is not assembled from
the character chunks and contains no artificial 200-character overlap.

### Manifest and cache validation

`manifest.json` records:

- extractor version;
- source directory;
- article count;
- complete source filename list;
- article title mapping;
- stored format description.

On startup, the cache is reused only when:

- the extractor version matches;
- the current source filename list matches the manifest;
- every expected text file exists.

If those conditions fail, the text collection is regenerated.

### Lazy article loading

`ArticleTextStore` keeps the source/title mapping in memory but does not load all 75 MB
of article content.

When retrieval identifies an article, `ArticleTextStore.load(source)` reads only that
article's `.txt` file.

---

## Markdown + structured sidecar collection

`build_or_load_markdown_store()` maintains a Markdown rendering plus a structured JSON
sidecar for every article. It exists to (a) preserve the formatting the plain-text
extraction discards — sections, infoboxes, tables, captions, and links — and (b) provide
the per-article relationships the Module 4 knowledge graph is built from.

### A separate, structure-aware extractor

Unlike the plain-text and chunk paths (standard-library `html.parser`, via
`extract_title_and_body`), this path parses the full DOM with **BeautifulSoup** (`lxml`)
and serializes prose to Markdown with **markdownify**. Those packages are imported
lazily inside `corpus.py`, so the BM25/vector/hybrid paths still import the module
without them installed. Required packages: `beautifulsoup4`, `markdownify`, `lxml`.

### Directory structure

```text
retrievers/db/article_text/wikipedia_markdown/
  manifest.json
  100_metres.html.md
  100_metres.html.json
  1580.html.md
  1580.html.json
  ...
```

Two files per article — the readable `.md` and its `.json` sidecar — keyed by the same
`source` filename used everywhere else (for example `1580.html`), so an article joins
across all corpus stores by that key.

### What the Markdown preserves

- the title as a level-1 heading (`# ...`);
- the infobox as a `## Infobox` bullet list of key → value fields;
- the h2–h6 section hierarchy as `##`/`###`/… headings;
- data tables (`table.wikitable`) as GitHub-flavored Markdown tables;
- blockquotes, nested lists, and image/figure captions (the image itself is dropped;
  its caption text is kept);
- inline links as `[anchor](/wiki/Target)` — kept in the body by design, since they read
  well and mark the article's relationships in place.

### What is removed before rendering

To keep both the prose and the extracted link list clean, page chrome is stripped from
the DOM *before* anything is read off it:

- navigation templates (`.navbox`, sidebars), the table of contents, and `[edit]` links;
- inline citation superscripts (`[1]`, `[2]`) and the reference/citation dump
  (`ol.references`, `.reflist`);
- maintenance banners (`.ambox`/`.mbox`/… — "needs citations", "translate from German");
- red links (to pages that do not exist) are converted to plain text.

**Ordering matters.** Chrome is removed before links are collected, so navigation and
citation links never enter the sidecar or the graph. An earlier ordering leaked roughly
twice as many links per article, dominated by navbox-footer links and DOI/PMID/ISBN
citation stubs.

### The structured sidecar

Each `.json` mirrors the shape of Lab 4.2's `annotatedEmails.json` (raw content plus
structured fields), so the knowledge graph can be built directly from it:

```json
{
  "source": "1854_Broad_Street_cholera_outbreak.html",
  "title": "1854 Broad Street cholera outbreak",
  "wiki_title": "1854_Broad_Street_cholera_outbreak",
  "categories": ["1854 in London", "1850s epidemics", "..."],
  "sections": [{"level": 2, "id": "Background", "title": "Background"}],
  "infobox": {"title": "", "fields": {"Date": "1854", "Deaths": "616"}},
  "tables": [{"caption": null, "headers": ["..."], "rows": [["..."]], "n_rows": 10}],
  "links": {
    "local":    [{"target": "John_Snow", "source_file": "John_Snow.html",
                  "url": "https://en.wikipedia.org/wiki/John_Snow",
                  "anchors": ["John Snow"], "count": 3, "regions": ["body"]}],
    "wiki":     [{"target": "Vibrio_cholerae",
                  "url": "https://en.wikipedia.org/wiki/Vibrio_cholerae",
                  "anchors": ["Vibrio cholerae"], "count": 2, "regions": ["body", "infobox"]}],
    "external": [{"url": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1508470",
                  "anchors": ["..."], "count": 1, "regions": ["body"]}]
  },
  "stats": {"n_categories": 19, "n_sections": 17, "n_tables": 0,
            "n_local": 4, "n_wiki": 62, "n_external": 8, "md_chars": 25024}
}
```

### Link classification (local / wiki / external)

Every `<a>` in the article body, infobox, and data tables is classified so that a later
step can tell what it can reference locally from what it would have to fetch:

- **local** — a `/wiki/<Target>` whose `<Target>.html` exists in this corpus. Carries
  `source_file`; these are the in-corpus article → article edges for the graph.
- **wiki** — a `/wiki/<Target>` not in the corpus (a real Wikipedia article this corpus
  does not hold). Carries the canonical `url`, so the article could be pulled later if
  desired. Even with the target absent, two articles that link the *same* wiki target are
  related, which makes shared wiki targets the densest "mentioned entity" signal.
- **external** — an off-wiki `http(s)` link (citation or official site). Carries `url`.

Namespaced links (`Category:`, `File:`, `Help:`, …) are not treated as article links;
categories are captured separately from the page's category box. Each link record also
keeps `anchors` (the visible link-text variants), a `count`, and the `regions` it
appeared in (`body`, `infobox`, `table`), so body links can later be weighted above
navigational ones.

### Manifest and cache validation

Like the plain-text store, `manifest.json` records the extractor version, source
directory, article count, source filename list, title mapping, and any per-article
extraction `failures`. The cache is reused only when the extractor version matches, the
source filename list matches, and both the `.md` and `.json` exist for every article;
otherwise the store is rebuilt. Bump `_MARKDOWN_EXTRACTOR_VERSION` when the extraction
rules change so stale output is regenerated on the next run.

### Lazy loading

`MarkdownArticleStore` keeps only the source → title mapping in memory:

- `load(source)` reads one article's `.md` + `.json` and returns a `MarkdownArticle`;
- `load_metadata(source)` reads just the sidecar;
- `iter_metadata()` streams `(source, sidecar)` for every article — the entry point the
  knowledge-graph builder consumes.

### Building

```bash
python retrievers/corpus.py            # build if absent, otherwise load from cache
python retrievers/corpus.py --force    # force a full rebuild
```

### Corpus statistics

The built store (extractor version 1) contains:

- **2,417 articles**, two files each, roughly **287 MB** total, with **0 extraction
  failures**;
- **infoboxes:** 2,004 articles (83%); **data tables:** 1,473 articles (61%);
- **per-article averages:** 20 sections, 15.5 categories, and about 41 KB of Markdown.

Link totals across the whole corpus:

| bucket | total links | meaning |
|---|---|---|
| `local` | 17,396 | in-corpus article → article edges |
| `wiki` | 571,784 | links to real articles not held in the corpus (pullable) |
| `external` | 22,882 | off-wiki citation / official-site links |

**Graph readiness.** These figures indicate the relationships are dense enough for
graph-augmented retrieval to add value:

- the in-corpus link graph has **17,396 directed edges**, and only **141 articles (6%)**
  have no in-corpus link at all;
- **80% of articles** share at least one category with another article, and shared
  categories connect roughly **130,000 article pairs**;
- treating every `/wiki/` target (including out-of-corpus ones) as a shared "entity"
  connects about **2.7 million article pairs** — the densest relatedness signal, and the
  reason the `wiki` bucket is worth keeping even though those targets are not local files.

The corpus is thematically concentrated — the densest categories are "Living people",
American actors and actresses, Grammy and Academy Award recipients, and Olympic sport —
so category and entity edges cluster strongly within those themes.

---

## Full-article retrieval experiment

The full-article experiment deliberately separates discovery from context assembly:

```text
Question
→ BM25/vector/hybrid searches baseline character chunks
→ top-k chunk IDs identify unique source articles
→ each selected article's complete .txt file is loaded once
→ complete article texts are sent to the LLM
```

The overlapping retrieval chunks are not sent as the final context and are not used to
reconstruct the article.

This design answers a specific experimental question: if retrieval found the correct
article, does complete article context improve broad synthesis compared with only
top-k chunks?

It does not solve article recall. If retrieval finds only a life-expectancy article and
misses the required population article, full-text loading cannot introduce the missing
article.

It may also produce very large context when several long articles are selected. The
evidence log records selected files and total context characters so this tradeoff can be
evaluated.

---

## Evidence and reproducibility

Each experiment log records:

- corpus article and chunk counts;
- chunking strategy and size/overlap settings;
- retriever configuration;
- Chroma database name and embedding model;
- context strategy;
- plain-text store location when full articles are used;
- retrieved article names and seed chunk IDs;
- exact full-article files sent to the LLM;
- context character count;
- grounded answer.

Keeping separate Chroma names and logging preprocessing settings makes comparisons
between character chunks, natural sections, and complete articles reproducible.
