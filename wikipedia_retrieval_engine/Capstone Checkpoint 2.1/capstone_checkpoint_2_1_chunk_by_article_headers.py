r"""Checkpoint 2.1 experiment: chunk Wikipedia articles by HTML section headings.
Jupytext-style cell markers (# %% / # %% [markdown]) — runnable as a
plain script AND openable as cells in VS Code / PyCharm / Jupytext.
"""

# %% [markdown]
# # Capstone Checkpoint 2.1 — Retrieval Strategy Design and Baseline Implementation
# **MO-LLM Module 2 / Required Capstone Checkpoint (120 minutes)**
#
# ## What this checkpoint is
#
# In Checkpoint 1.1, you showed that a plain LLM can't reliably answer questions about
# your corpus. Now, you will **add retrieval**: Design a retrieval strategy for your scenario
# and build a **baseline retrieval system** that finds the most relevant documents for
# a query, so the model can ground its answers in them.
#
# This mirrors the Module 2 labs — keyword (BM25), vector (semantic), and hybrid
# retrieval — applied to your own capstone corpus. The graded deliverable is the completed 
# Capstone Checkpoint 2.1 worksheet, which includes your written responses and evidence of your 
# retrieval system implementation and testing. This script provides a small working example of 
# baseline retrieval. Use it to understand the retrieval workflow, then adapt the code to implement 
# and test a baseline retriever using your selected capstone dataset.
#
# **Learning outcomes (Module 2):**
# 1. Design a retrieval strategy appropriate for a given dataset and query type.
# 2. Implement and test a baseline retrieval system using structured and/or semantic
#    approaches.

# %% [markdown]
# ## Step 1 — Keep your capstone scenario
#
# Use the **same scenario** you chose in Checkpoint 1.1.
#
# | Scenario | Corpus | Retrieval considerations |
# |---|---|---|
# | **Research Paper Navigator** | ~150 research-paper PDFs (`Labs/CapstoneDatasets/ResearchPapers/`) | long documents; you'll likely chunk them; questions often name a specific paper or compare papers. |
# | **Wikipedia Retrieval Engine** | ~2,400 Wikipedia HTML articles (`Labs/CapstoneDatasets/Wikipedia/`) | many short-to-medium articles; questions name a figure/place or span several articles. |
#
# A good baseline is keyword (BM25), semantic (embeddings + vector search), or a
# hybrid of both — exactly what you built in Labs 1.2–2.2.

# %% [markdown]
# ## Setup (~5 min)
#
# 1. **Python 3.11 or 3.12**
# 2. `pip install langchain-openai langchain-core python-dotenv`
# 3. Use the OpenRouter API key provided for this program. This checkpoint uses
#  the `openai/gpt-5.4-mini` model, with usage covered by the course credits. (this uses the paid gpt-5.4-mini chat model — covered by your course credits — and a keyword retriever, no embeddings).
# 4. Create a `.env` file next to this script: `OPENROUTER_API_KEY=sk-or-v1-...`
#
# This runs on a tiny built-in sample corpus, so you do not need to prepare your own
# dataset. It still requires an OpenRouter API key to run the LLM (it is not offline or
# free of API calls). Your real baseline (over your full corpus) is what you describe in
# the writeup.

# %%
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import re
import sys
from datetime import datetime
from pathlib import Path

try:
    _HERE = Path(__file__).resolve().parent
except NameError:
    _HERE = Path.cwd()
_ENGINE = _HERE.parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from retrievers import (
    EvidenceLogger,
    RetrieverSpec,
    build_or_load_db,
    format_articles,
    format_chunks,
    load_wikipedia_section_chunks,
    make_retriever,
)
from retrievers.corpus import DEFAULT_WIKI_DIR
from retrievers.llm import answer as answer_from_context
from retrievers.llm import make_llm

# %%
SAMPLE_TOP_K = 3
RETRIEVAL_TOP_K = 10
HYBRID_CANDIDATE_POOL = max(10, RETRIEVAL_TOP_K)
MAX_SECTION_CHARS = 10000
SECTION_OVERLAP = 0
CHROMA_DB_NAME = "wikipedia_sections_max10000_no_overlap"
CHUNKING_STRATEGY = "article_headers"
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
LOG_DIR = _HERE / "logs"
SAMPLE_LOG_PATH = LOG_DIR / f"{RUN_ID}__toy-baseline.log"

# List to compare retrievers / knobs.
# Natural chunks follow Wikipedia h2–h6 headings. A section is split without overlap
# only when it exceeds MAX_SECTION_CHARS, keeping embeddings within a practical size.
# Vector/hybrid persist this distinct index under retrievers/db/CHROMA_DB_NAME.

EXPERIMENTS = [
    RetrieverSpec(kind="vector", label=f"vector_k{RETRIEVAL_TOP_K}", top_k=RETRIEVAL_TOP_K),
    RetrieverSpec(kind="hybrid", label="hybrid_vector_heavy", top_k=RETRIEVAL_TOP_K,
                  candidate_pool=HYBRID_CANDIDATE_POOL,
                  weight_bm25=0.35, weight_vector=0.65),
]

SCENARIO = "wikipedia"  


def log(label: str, text: str) -> None:
    ts = datetime.now().isoformat(timespec="seconds")
    SAMPLE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with SAMPLE_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(f"[{ts}] {label}\n{text}\n{'-' * 72}\n")




# %% [markdown]
# ## Step 2 — The baseline retriever (provided)
#
# A simple keyword-overlap retriever scores each document by how many query words
# it shares, and returns the top-k. This is the smallest possible baseline (a stand-in
# for the BM25 / vector / hybrid retriever you built in the Module 2 labs). The
# `answer` function then asks the LLM using only the retrieved documents.

# %%
def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def retrieve(query: str, k: int = SAMPLE_TOP_K) -> list[tuple[str, float]]:
    """Baseline keyword retrieval: Score each doc by shared-word count, return top-k."""
    q = _tokens(query)
    scored = [(d["id"], float(len(q & _tokens(d["text"])))) for d in SAMPLE_DOCS]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(doc_id, score) for doc_id, score in scored[:k] if score > 0]


def sample_context(doc_ids: list[str]) -> str:
    context = "\n\n".join(f"[{i}] {DOC_BY_ID[i]['text']}" for i in doc_ids if i in DOC_BY_ID)
    return context


# %% [markdown]
# ## Step 3 — Your representative queries 
#
# Submission item #2 asks for **3-5 representative queries** for your scenario and the
# results your system retrieves for each. Write those queries here. Some good ones include questions that:
#
# - Are answerable from **one** document (tests precision),
# - Need **several** documents (tests recall / aggregation),
# - Have wording that **differs** from the document's wording (i.e., tests whether
#   keyword vs. semantic retrieval matters for your corpus)
#
# Return a list of 3-5 query strings.

# %%
def my_representative_queries() -> list[str]:
    questions = [              
        "According to the Wikipedia article on the 100 meters, what is the "
        "current men's world record, who holds it, and when was it set? "
        "Quote the article.",
        "List three significant events recorded in the Wikipedia article for "
        "the year 1580, quoting the article for each.",
        "Was there a person who was nominated for academy award in all three 68th, 70th and 74th awards?",
        "Where were 1972 Winter Olympics held?",
        "Which country got the most medals in 1972 Winter Olympics?",
        "How does nomination process work in academy awards?",
        "Which actor has won the most academy awards between from 2000 to 2020?",
        "What were the most devastating earthquakes in the last 50 years? Show human deaths for each earthquake.",
        "Compare countries by their life expectancy vs. population. Is there a correlation?",
        "For winter olympics, list events that were added in the last 100 years in order they were added listing the year they were added.",
        "For summer olympics, list events that were added in the last 100 years in order they were added listing the year they were added and the country that the olympics were held in at that time.",
        "Which winter/summer olympic years, Russia hosted the olympics?",
        "Which olympics, Russia did not participate in?"
    ]
    return questions



def run_wikipedia() -> None:
    """Compare configurable retrievers on the real Wikipedia corpus and log evidence."""
    if not EXPERIMENTS:
        raise RuntimeError("EXPERIMENTS is empty. Add at least one RetrieverSpec.")
    queries = my_representative_queries()
    needs_vector = any(spec.kind in {"vector", "hybrid"} for spec in EXPERIMENTS)
    print("Loading Wikipedia sections...")
    chunks = load_wikipedia_section_chunks(
        max_section_chars=MAX_SECTION_CHARS,
        overlap=SECTION_OVERLAP,
    )
    db = (
        build_or_load_db(chroma_db_name=CHROMA_DB_NAME, chunks=chunks)
        if needs_vector
        else None
    )

    retrievers = [
        make_retriever(
            spec,
            chunks=chunks,
            db=db,
            chroma_db_name=CHROMA_DB_NAME,
        )
        for spec in EXPERIMENTS
    ]
    evidence_logs = [
        EvidenceLogger(
            log_dir=LOG_DIR,
            run_id=RUN_ID,
            retriever=retriever,
            chunks=chunks,
            question_count=len(queries),
            chroma_db_name=CHROMA_DB_NAME,
            chunking_strategy=CHUNKING_STRATEGY,
            chunk_size=MAX_SECTION_CHARS,
            chunk_overlap=SECTION_OVERLAP,
            wiki_dir=DEFAULT_WIKI_DIR,
        )
        for retriever in retrievers
    ]
    llm = make_llm()
    print(f"Checkpoint 2.1 — Wikipedia retrieval  |  scenario: {SCENARIO}")
    print(f"Experiments: {[r.label for r in retrievers]}")
    print("Evidence logs:")
    for evidence_log in evidence_logs:
        print(f"  {evidence_log.path}")
    print()

    for i, query in enumerate(queries, 1):
        print("=" * 72)
        print(f"QUERY {i}: {query}")
        for retriever, evidence_log in zip(retrievers, evidence_logs):
            hits = retriever.getTopK(query)
            settings = retriever.settings()
            print(f"\n  [{retriever.label}] settings={settings}")
            print("  Retrieved articles:")
            print(format_articles(hits))
            print("  Retrieved chunks:")
            print(format_chunks(hits, snippet_chars=220))
            if not hits:
                evidence_log.log_question(
                    number=i,
                    query=query,
                    hits=hits,
                    answer="(skipped because no chunks were retrieved)",
                )
                continue
            # Reuse the exact hits displayed and logged; do not retrieve a second time.
            context = retriever.format_context(hits)
            ans = answer_from_context(query, context, llm=llm)
            print(f"  answer: {ans}\n")
            evidence_log.log_question(
                number=i,
                query=query,
                hits=hits,
                answer=ans,
            )
    print("=" * 72)
    print("Done. Use the timestamped log as evidence in your writeup.")


if __name__ == "__main__":
    run_wikipedia()
    # run_sample_corpus()  # optional: original 6-document toy baseline

# %% [markdown]
# ## Step 5 — Your written submission (the graded deliverable)
#
# Use your completed retrieval implementation and test results to complete the Capstone Checkpoint 2.1
# worksheet. In the worksheet, you will document your retrieval approach, provide evidence that your 
# system is functioning, include 3–5 representative queries and retrieved results, and reflect on where
# your approach performs well and where it struggles.  
 
# Save your completed Python file in the appropriate checkpoint folder in your GitHub repository. 
# Upload the completed worksheet only to the learning platform as your graded submission.
