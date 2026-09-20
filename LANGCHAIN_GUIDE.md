# LangChain tutorial, reference, and gotchas

This is a Python-first learning and reference guide. Its examples reflect the
versions pinned in this repository's `requirements.txt`, especially
`langchain-core 1.3`, `langchain-openai 1.1`, and `langchain-chroma 1.1`.

Read it independently to brush up on LangChain, LCEL, retrieval, structured output,
tools, and LangGraph. Project links are included as concrete examples, while
checkpoint-specific decisions and experiment notes live in the checkpoint READMEs.

LangChain changes quickly. Treat the pinned requirements as the project's API
contract; do not combine examples copied from older tutorials with this environment
without checking their imports.

Suggested reading path:

- sections 1–5 for LangChain fundamentals and runnable execution;
- sections 6–8 for documents, embeddings, Chroma, and transparent RAG;
- sections 9–10 for structured output and tools;
- sections 12–14 when debugging or migrating older examples; and
- section 15 for LangGraph state, routing, persistence, and memory.

## 1. The useful mental model

LangChain is not one monolithic package. In this project it provides a few small,
composable interfaces:

- **Messages** represent chat input and output (`SystemMessage`, `HumanMessage`,
  `AIMessage`).
- **Prompt templates** turn application data into messages.
- **Chat models** turn messages into an `AIMessage`.
- **Embeddings** turn text into numeric vectors.
- **Documents** carry `page_content` plus `metadata`.
- **Vector stores** save and search embedded documents.
- **Runnables / LCEL** compose those pieces with `|` and expose a common execution
  interface: `invoke`, `ainvoke`, `batch`, `abatch`, `stream`, and `astream`.

For this capstone, retrieval and answer generation should remain visibly separate:

```text
question -> retrieve chunks -> inspect/log hits -> build context -> prompt model -> answer
```

That boundary matters. It makes retrieval quality measurable, prevents an opaque
chain from retrieving twice, and ensures evaluation logs contain the exact evidence
shown to the answer model.

## 2. Package and import map

- Messages, prompts, documents, and runnables: `langchain-core`, imported through
  `langchain_core...`.
- OpenAI-compatible chat and embeddings: `langchain-openai`, typically
  `from langchain_openai import ChatOpenAI, OpenAIEmbeddings`.
- Chroma adapter: `langchain-chroma`, imported with
  `from langchain_chroma import Chroma`.
- Community integrations: `langchain-community`, imported through
  `langchain_community...`.
- Text splitting: `langchain-text-splitters`, imported through
  `langchain_text_splitters...`.
- High-level agents: `langchain` (not currently pinned here), with
  `from langchain.agents import create_agent`.

Gotcha: installing `langchain-core` does not install every provider or vector-store
adapter. Integration packages are intentionally separate. Prefer provider-specific
imports over old examples that import everything from `langchain`.

## 3. Setup and provider configuration

From `rag_and_context_engineering/`:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Put the course key in `.env` and never commit it:

```text
OPENROUTER_API_KEY=sk-or-v1-...
```

This project uses OpenRouter's OpenAI-compatible endpoint. The client therefore
comes from `langchain-openai`, but the key, base URL, and model name are OpenRouter
values:

```python
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

model = ChatOpenAI(
    model="openai/gpt-5.4-mini",
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
    temperature=0.2,
    timeout=60,
    max_retries=3,
)
```

Gotcha: `OPENROUTER_API_KEY` is not automatically treated as `OPENAI_API_KEY`.
Passing `api_key` explicitly, as this repository does, avoids ambiguity.

Current LangChain documentation also describes a dedicated
[`langchain-openrouter` integration](https://docs.langchain.com/oss/python/integrations/chat/openrouter).
This repository intentionally uses its pinned `langchain-openai` compatibility path.
Do not mix the two imports without updating requirements and rerunning integration
tests.

## 4. First model call: messages in, message out

```python
from langchain_core.messages import HumanMessage, SystemMessage

response = model.invoke(
    [
        SystemMessage(content="Answer only from supplied evidence."),
        HumanMessage(content="Evidence: Paris is in France.\nQuestion: Where is Paris?"),
    ]
)

print(response.content)
print(response.usage_metadata)       # provider-dependent token usage
print(response.response_metadata)    # provider-dependent request/model details
```

`invoke` returns an `AIMessage`, not a string. Use `.content` when the application
requires text. Content may be a list of typed blocks for multimodal or reasoning
models, so production code should not assume it is always a plain string.

### Prompt templates and LCEL

```python
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "Answer only from the context. Say when evidence is insufficient."),
        ("human", "Context:\n{context}\n\nQuestion: {question}"),
    ]
)

chain = prompt | model | StrOutputParser()
answer = chain.invoke(
    {"context": "Paris is the capital of France.", "question": "What is France's capital?"}
)
```

Each side of `|` is a runnable. The output shape of one stage must match the input
shape of the next. Here, the prompt emits messages, the model emits an `AIMessage`,
and `StrOutputParser` emits a string.

## 5. Runnable execution reference

```python
# One input, synchronous
value = chain.invoke(input_data)

# One input, asynchronous
value = await chain.ainvoke(input_data)

# Many inputs; concurrency is managed by the runnable
values = chain.batch([input_a, input_b])
values = await chain.abatch([input_a, input_b])

# Incremental output (support varies by component/provider)
for chunk in chain.stream(input_data):
    print(chunk, end="")

async for chunk in chain.astream(input_data):
    print(chunk, end="")
```

Useful configuration:

```python
results = await chain.abatch(
    inputs,
    config={"max_concurrency": 4, "tags": ["checkpoint-4.1"]},
    return_exceptions=True,
)
```

Gotchas:

- `batch` improves orchestration, but a provider may still receive separate API
  calls rather than one native batch request.
- Unlimited concurrency can trigger rate limits. Bound it deliberately.
- `return_exceptions=True` keeps one failed input from aborting the whole batch, but
  every result must then be checked for `Exception`.
- Do not call `asyncio.run()` from an environment that already owns an event loop
  (commonly notebooks). Use `await` there.

## 6. Documents, splitting, and metadata

```python
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

articles = [
    Document(
        page_content="A long article...",
        metadata={"source": "Paris.html", "title": "Paris"},
    )
]

splitter = RecursiveCharacterTextSplitter(chunk_size=1600, chunk_overlap=200)
chunks = splitter.split_documents(articles)
```

Metadata survives splitting and is how retrieved text is mapped back to its source.
Keep stable fields such as `source`, `title`, `article`, `section_title`, and a chunk
identifier. Metadata values should be scalar, serializable types accepted by the
chosen vector store.

Gotchas:

- `chunk_size` is measured by the splitter's length function—characters by default,
  not tokens. Use a tokenizer-aware splitter when token limits are the constraint.
- Large overlap increases index size and duplicate evidence. Small or zero overlap
  can split facts away from their headings or qualifiers.
- Splitting raw HTML before cleaning preserves navigation noise and can break tables.
  This repo first builds structure-preserving Markdown plus a JSON sidecar.
- Preserve article and section identity during ingestion; reconstructing provenance
  from chunk text later is unreliable.

## 7. Embeddings and Chroma

```python
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

embeddings = OpenAIEmbeddings(
    model="openai/text-embedding-3-small",
    api_key=os.environ["OPENROUTER_API_KEY"],
    base_url="https://openrouter.ai/api/v1",
)

db = Chroma(
    collection_name="wikipedia_chars1600_overlap200",
    persist_directory="retrievers/db/wikipedia_chars1600_overlap200",
    embedding_function=embeddings,
)

ids = db.add_documents(chunks)
docs = db.similarity_search("Who designed the Eiffel Tower?", k=4)
scored = db.similarity_search_with_score("Who designed the Eiffel Tower?", k=4)
```

You can expose a vector store through the common retriever interface:

```python
retriever = db.as_retriever(search_kwargs={"k": 4})
docs = retriever.invoke("Who designed the Eiffel Tower?")
```

### Chroma gotchas

- **Score direction is not universal.** `similarity_search_with_score` can return a
  distance for which lower is better. `similarity_search_with_relevance_scores`
  aims for a normalized relevance score for which higher is better. Verify the
  chosen store, distance metric, adapter version, and method before fusing scores.
  This repository's Chroma path treats raw scores as distances and inverts them
  during normalization.
- **An embedding model is part of the index schema.** Query with the same model and
  dimensionality used to build the collection. Changing it requires a new index.
- **Chunking is also part of the index schema.** A directory name should encode the
  chunking strategy so incompatible experiments do not silently reuse an old index.
- **Stable IDs prevent duplicates.** Re-running `add_documents` without explicit,
  deterministic IDs can insert the same corpus again.
- **An existing directory is not proof of a complete index.** A process can fail
  halfway through ingestion. Store and validate a manifest with corpus hash, count,
  embedding model, splitter settings, and build status.
- **Persistence is local state.** Do not assume the same Chroma directory is safe for
  concurrent writers, portable across incompatible Chroma versions, or suitable as
  a production multi-user database.
- **Metadata filters are exact and backend-specific.** Normalize values during
  ingestion and test filters against the installed adapter.

## 8. A transparent RAG pattern

For evaluation work, an explicit function is often clearer than a deeply nested
chain:

```python
from langchain_core.messages import HumanMessage, SystemMessage

SYSTEM = """Answer only from the supplied context. If it is insufficient, say so.
Cite the source title for every factual claim."""


def format_docs(docs: list[Document]) -> str:
    return "\n\n".join(
        f"SOURCE: {doc.metadata.get('title', doc.metadata.get('source', 'unknown'))}\n"
        f"{doc.page_content}"
        for doc in docs
    )


def answer_question(question: str) -> tuple[str, list[Document]]:
    docs = retriever.invoke(question)
    context = format_docs(docs)
    response = model.invoke(
        [
            SystemMessage(content=SYSTEM),
            HumanMessage(content=f"Context:\n{context}\n\nQuestion: {question}"),
        ]
    )
    return str(response.content), docs
```

Why return the documents too? The caller can log evidence, compute retrieval recall,
show citations, and distinguish retrieval failure from answer-generation failure.

### Optional all-runnable form

```python
from operator import itemgetter

from langchain_core.runnables import RunnableLambda, RunnablePassthrough

rag_chain = (
    {
        "context": itemgetter("question") | retriever | RunnableLambda(format_docs),
        "question": itemgetter("question"),
    }
    | prompt
    | model
    | StrOutputParser()
)

answer = rag_chain.invoke({"question": "Who designed the Eiffel Tower?"})
```

This is compact, but it hides retrieved documents unless the graph is designed to
carry them forward. Prefer the explicit form when retrieval diagnostics are a first-
class output.

## 9. Structured output

Use a schema when downstream code needs data rather than prose:

```python
from pydantic import BaseModel, Field


class GroundedAnswer(BaseModel):
    answer: str
    source_titles: list[str] = Field(default_factory=list)
    evidence_sufficient: bool


structured_model = model.with_structured_output(GroundedAnswer)
result = structured_model.invoke(
    "Paris is the capital of France. Answer: What is France's capital?"
)

print(result.answer)
```

Gotchas:

- Support and implementation vary by model/provider. Some use native JSON schema;
  others simulate structured output through tool calling.
- Schema validation improves shape, not truth. A perfectly valid object can contain
  an unsupported claim or invented citation.
- Keep schemas small and descriptions precise. Complex nested schemas increase
  latency and failure rates.
- During debugging, use `include_raw=True` when supported so parsing failures and the
  original `AIMessage` are inspectable.

## 10. Tool calling is a two-step protocol

```python
from langchain_core.tools import tool


@tool
def lookup_article(title: str) -> str:
    """Return an article by its exact title."""
    return local_article_store[title]


tool_model = model.bind_tools([lookup_article])
ai_message = tool_model.invoke("Look up Paris and summarize it.")
print(ai_message.tool_calls)
```

Binding tools tells the model what it may request. It does not necessarily execute
the Python function. A tool loop must validate the request, execute the tool, append
a matching `ToolMessage` with the correct call ID, and ask the model to continue. Use
the high-level `create_agent` API only if the `langchain` package is deliberately
added and an agent loop is actually needed.

Gotchas:

- Treat tool arguments as untrusted input.
- Tool docstrings influence selection; vague descriptions cause poor routing.
- Enforce timeouts, size limits, and authorization in tool code.
- Do not use an agent when a fixed retrieve-then-answer workflow is sufficient. A
  deterministic workflow is easier to evaluate and usually cheaper.

## 11. Error handling, retries, and observability

Set timeouts and retries on clients rather than wrapping every call in an unbounded
retry loop. Retry transient network, rate-limit, and server errors; do not retry bad
credentials or invalid requests indefinitely.

For every evaluated request, record at least:

- run/configuration name and timestamp;
- model and embedding model;
- prompt version;
- corpus/index version and retrieval settings;
- retrieved document IDs and raw scores;
- exact context sent to the model;
- response, latency, token usage, and exception type.

Never log API keys. Be cautious with prompts or traces that contain private source
documents. LangSmith tracing is optional and sends trace data to an external service;
enable it only when that data flow is acceptable.

## 12. Common migration traps

### Old chains and agents

Older tutorials commonly use `LLMChain`, `RetrievalQA`, `ConversationalRetrievalChain`,
`initialize_agent`, or `AgentExecutor`. Modern examples favor runnable composition for
workflows and `create_agent` for agents. Some legacy APIs may live in
`langchain-classic`, which this project does not need.

### Moved imports

An old tutorial may import a provider, loader, splitter, or vector store from a path
that no longer owns it. Use integration packages (`langchain_openai`,
`langchain_chroma`) and `langchain_core` primitives. Match examples to the installed
major versions.

### `.run`, `.predict`, and callable chains

Prefer the uniform runnable methods `invoke` / `ainvoke` / `batch` / `stream`.
They make input and output shapes explicit and compose consistently.

### Memory is not magic

A model call is stateless unless prior messages or persisted state are supplied.
Do not pass an unlimited transcript: it raises cost, can exceed the context window,
and allows stale or malicious content to dominate. For a simple chat, explicitly
store and trim messages. For durable, branching agent state, use LangGraph rather
than an old buffer-memory tutorial.

### Version drift

LangChain integration packages and their dependencies release independently. Avoid
casually upgrading one package in the pinned environment. Create a branch or fresh
environment, upgrade the compatible set, run import smoke tests, rebuild disposable
indexes, and rerun retrieval plus answer-quality evaluations.

## 13. RAG gotchas that LangChain cannot solve for you

- **Retrieval relevance is not answer correctness.** Evaluate retrieval and
  generation separately.
- **Top-k is a budget, not a quality guarantee.** More chunks can bury the answer,
  repeat text, and exceed model limits.
- **Vector search misses exact terms.** IDs, rare names, dates, and quotations often
  benefit from BM25 or hybrid retrieval.
- **Chunk recall differs from source recall.** A relevant article can be present but
  the required section absent. Track both.
- **Naive score fusion is invalid.** BM25 scores, vector distances, and relevance
  scores are on different scales and sometimes opposite directions. Normalize or
  use rank-based fusion.
- **Prompt injection can live in documents.** Retrieved text is data, not trusted
  instructions. Delimit it clearly and do not give it authority over system rules.
- **Citations must be derived from retrieved metadata.** Asking the model to invent a
  bibliography from memory is not provenance.
- **Context windows include everything.** System text, question, retrieved content,
  message history, tool schemas, and output allowance all consume tokens.
- **Evaluation judges are models too.** Pin judge model/prompt, retain raw judgments,
  use question-specific rubrics, and manually audit samples.

## 14. Practical debugging checklist

When a RAG answer is wrong, inspect in this order:

1. Was the correct source present in the corpus and parsed correctly?
2. Did the query target the vocabulary used in that source?
3. Was the required article retrieved?
4. Was the required passage retrieved, not merely the article?
5. Were scores interpreted in the correct direction?
6. Was evidence lost during deduplication, expansion, truncation, or formatting?
7. Did the exact context sent to the model contain the answer?
8. Did the prompt require grounding, completeness, and honest abstention?
9. Did the model follow the prompt?
10. Is the evaluator's judgment correct and reproducible?

This sequence prevents a common failure mode: changing the prompt when the answer was
never retrieved, or changing retrieval when the model ignored adequate evidence.

## 15. Agentic workflows with LangGraph

There are two different meanings of “graph” in this project:

- The existing **NetworkX knowledge graph** represents Wikipedia entities and
  relationships. It is data used by `GraphRetriever` to find evidence.
- A **LangGraph workflow graph** represents control flow. Its nodes run retrieval,
  grading, query rewriting, answer generation, or tools; its edges decide what runs
  next; and its state carries data between those steps.

They can work together: a LangGraph node can call the existing graph retriever, but
LangGraph does not replace the knowledge graph.

### When a workflow becomes agentic

A fixed pipeline always follows the same route:

```text
retrieve -> answer
```

An adaptive or agentic pipeline uses model output or runtime evidence to select its
next action:

```text
initialize -> retrieve -> grade evidence -- sufficient --> answer -> END
                              |
                         insufficient
                              |
                              v
                           rewrite ---------> retrieve
```

Use deterministic code for constraints—attempt limits, permissions, required state,
and terminal conditions. Use an LLM only where semantic judgment is valuable, such
as grading whether evidence answers a question or rewriting an ambiguous query.

### Installation

LangGraph is distributed separately from the core LangChain packages:

```bash
pip install -U langgraph
```

In a reproducible project, pin the exact tested version alongside the compatible
LangChain packages. This repository's Checkpoint 5.1 README records its own dependency
and implementation status.

### Core vocabulary

- **State** is a typed shared snapshot. It should contain data, not open database or
  model clients.
- **Node** is a function that reads state and returns a partial state update.
- **Edge** is a fixed transition between nodes.
- **Conditional edge** runs a routing function and chooses the next node.
- **Reducer** defines how a field combines old and new values. Without a reducer, a
  new value replaces the old one.
- **START** and **END** are virtual entry and terminal nodes.
- **Compile** validates and creates the runnable graph. A builder is not executable
  until `compile()` is called.
- **Checkpointer** stores state snapshots for a thread so execution can resume.

### Worked example: an adaptive RAG graph

The following example reuses this repository's retriever and model boundaries as a
concrete illustration. It exposes retrieved documents in final state for evaluation
and permits at most three retrieval attempts. The project-specific design that grows
from this pattern is documented in
[`Capstone Checkpoint 5.1/README 5.1.md`](wikipedia_retrieval_engine/Capstone%20Checkpoint%205.1/README%205.1.md).

```python
from typing import Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from retrievers.llm import make_llm
from retrievers.vector import VectorRetriever

MAX_RETRIEVAL_ATTEMPTS = 3

llm = make_llm()
retriever = VectorRetriever(top_k=7)


class EvidenceGrade(BaseModel):
    sufficient: bool = Field(
        description="True only when the evidence can support a complete answer."
    )
    reason: str


class RAGState(TypedDict, total=False):
    question: str
    search_query: str
    documents: list[Document]
    attempts: int
    evidence_sufficient: bool
    grade_reason: str
    answer: str


def initialize(state: RAGState) -> RAGState:
    return {
        "search_query": state["question"],
        "attempts": 0,
        "documents": [],
    }


def retrieve(state: RAGState) -> RAGState:
    # This adapter returns tuples, so convert them to standard Documents. If the
    # underlying Chroma retriever is exposed directly, it can return Documents.
    hits = retriever.getTopK(state["search_query"])
    documents = [
        Document(
            page_content=text,
            metadata={"source": source, "raw_score": score},
        )
        for source, text, score in hits
    ]
    return {"documents": documents, "attempts": state["attempts"] + 1}


def format_documents(documents: list[Document]) -> str:
    return "\n\n".join(
        f"SOURCE: {doc.metadata.get('source', 'unknown')}\n{doc.page_content}"
        for doc in documents
    )


def grade_evidence(state: RAGState) -> RAGState:
    grader = llm.with_structured_output(EvidenceGrade)
    grade = grader.invoke(
        [
            SystemMessage(
                content=(
                    "Grade only whether the supplied evidence is sufficient to "
                    "answer the complete question. Do not answer the question."
                )
            ),
            HumanMessage(
                content=(
                    f"Question: {state['question']}\n\n"
                    f"Evidence:\n{format_documents(state['documents'])}"
                )
            ),
        ]
    )
    return {
        "evidence_sufficient": grade.sufficient,
        "grade_reason": grade.reason,
    }


def route_after_grade(state: RAGState) -> Literal["rewrite", "answer"]:
    if state["evidence_sufficient"] or state["attempts"] >= MAX_RETRIEVAL_ATTEMPTS:
        return "answer"
    return "rewrite"


def rewrite_query(state: RAGState) -> RAGState:
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "Rewrite the search query to retrieve missing Wikipedia "
                    "evidence. Return only the rewritten query."
                )
            ),
            HumanMessage(
                content=(
                    f"Original question: {state['question']}\n"
                    f"Previous query: {state['search_query']}\n"
                    f"Why evidence was insufficient: {state['grade_reason']}"
                )
            ),
        ]
    )
    return {"search_query": str(response.content).strip()}


def generate_answer(state: RAGState) -> RAGState:
    response = llm.invoke(
        [
            SystemMessage(
                content=(
                    "Answer only from the supplied evidence. Cite source IDs. "
                    "If evidence is still insufficient, explicitly abstain."
                )
            ),
            HumanMessage(
                content=(
                    f"Question: {state['question']}\n\n"
                    f"Evidence:\n{format_documents(state['documents'])}"
                )
            ),
        ]
    )
    return {"answer": str(response.content)}


builder = StateGraph(RAGState)
builder.add_node("initialize", initialize)
builder.add_node("retrieve", retrieve)
builder.add_node("grade", grade_evidence)
builder.add_node("rewrite", rewrite_query)
builder.add_node("answer", generate_answer)

builder.add_edge(START, "initialize")
builder.add_edge("initialize", "retrieve")
builder.add_edge("retrieve", "grade")
builder.add_conditional_edges("grade", route_after_grade)
builder.add_edge("rewrite", "retrieve")
builder.add_edge("answer", END)

rag_graph = builder.compile()

result = rag_graph.invoke(
    {"question": "Which sources support the answer?"},
    config={"recursion_limit": 15},
)
print(result["answer"])
print(result["attempts"], result["documents"])
```

This is “agentic” in a constrained sense: a semantic grader influences routing and a
query can be revised, but application code owns the allowed actions and termination
rules. That is a good fit for a graded RAG checkpoint because behavior remains
inspectable and bounded.

### State and reducer gotchas

Nodes should return only their updates, not mutate the incoming state in place. In
the example, each new retrieval result replaces `documents`, because no reducer is
declared. To accumulate values, annotate a field with a reducer:

```python
from operator import add
from typing import Annotated


class TraceState(TypedDict):
    events: Annotated[list[str], add]
```

Then a node can return `{"events": ["retrieved"]}` and LangGraph appends it. Be
careful: returning an empty list does not clear a reducer-backed list; it merely adds
nothing. Append-only documents and messages can also grow without bound, duplicate
context, and inflate checkpoints.

Further state rules:

- Store serializable values when using persistence. Recreate model, retriever, and
  database clients outside state or inject them through runtime context.
- Keep state fields explicit enough to evaluate: original question, active query,
  attempts, retrieved IDs/scores, routing decision, final answer, and errors.
- Do not put secrets in state. Checkpoints and streamed snapshots may expose it.
- Parallel nodes that update the same field require a reducer or will conflict.

### Loops must have two safety mechanisms

Every loop needs a business-level terminal condition, such as `attempts >= 3`, plus
a runtime backstop:

```python
from langgraph.errors import GraphRecursionError

try:
    result = rag_graph.invoke(inputs, config={"recursion_limit": 15})
except GraphRecursionError:
    result = {"answer": "The workflow exceeded its safe step limit."}
```

`recursion_limit` counts graph super-steps, not Python recursion or just retrieval
attempts. Set it high enough for the longest valid path, but never use it as the only
termination rule.

### Persistence and conversation threads

For an in-process prototype:

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
rag_graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "evaluation-GT01"}}
result = rag_graph.invoke({"question": "..."}, config=config)
```

A checkpointer saves graph snapshots within one `thread_id`; it is useful for resume,
human review, and thread-scoped memory. A LangGraph store is a separate abstraction
for application data shared across threads.

### `InMemoryStore`: application memory across threads

`InMemorySaver` and `InMemoryStore` solve different problems:

- `InMemorySaver` is controlled by the graph runtime. It checkpoints evolving graph
  state and locates it through invocation configuration such as `thread_id`.
- `InMemoryStore` is controlled by application or node code. It stores explicit
  key/value items in hierarchical namespaces and can be shared across threads.

For example, two conversation threads for the same user can use different
checkpoints while reading the same saved user preference from a store. “Across
threads” does not mean “across process restarts”: both classes are memory-only.

#### Direct key/value operations

```python
from langgraph.store.memory import InMemoryStore

store = InMemoryStore()

namespace = ("users", "user-123", "preferences")
store.put(namespace, "answer-style", {"verbosity": "concise", "citations": True})

item = store.get(namespace, "answer-style")
if item is not None:
    print(item.value["verbosity"])

items = store.search(namespace, filter={"citations": True}, limit=10)
store.delete(namespace, "answer-style")
```

The logical address is `(namespace, key)`. A namespace is a tuple of strings, not a
slash-delimited path. `put` values must be dictionaries with JSON-serializable data.
`get` returns an `Item` or `None`; the stored dictionary is in `.value`.

Design namespaces around ownership and purpose:

```python
("users", user_id, "preferences")
("users", user_id, "memories")
("evaluation", experiment_id, "feedback")
```

Never let an LLM choose an unrestricted namespace or user ID. Derive authorization
scope from trusted application context so one user cannot read or overwrite another
user's records.

#### Give graph nodes access to the store

Compile the graph with `store=...`. A node can receive the LangGraph runtime and use
`runtime.store`; runtime context carries trusted invocation data that should not be
saved as mutable graph state:

```python
from dataclasses import dataclass

from langgraph.runtime import Runtime


@dataclass(frozen=True)
class RequestContext:
    user_id: str


class PersonalizedState(TypedDict, total=False):
    question: str
    answer_style: str


def load_preferences(
    state: PersonalizedState,
    runtime: Runtime[RequestContext],
) -> PersonalizedState:
    namespace = ("users", runtime.context.user_id, "preferences")
    item = runtime.store.get(namespace, "answer-style") if runtime.store else None
    style = item.value["verbosity"] if item else "concise"
    return {"answer_style": style}


personalized_builder = StateGraph(
    PersonalizedState,
    context_schema=RequestContext,
)
personalized_builder.add_node("load_preferences", load_preferences)
personalized_builder.add_edge(START, "load_preferences")
personalized_builder.add_edge("load_preferences", END)

personalized_graph = personalized_builder.compile(store=store)
result = personalized_graph.invoke(
    {"question": "What did the retrieved evidence establish?"},
    context=RequestContext(user_id="user-123"),
)
```

The same store and a checkpointer can be supplied together:

```python
rag_graph = builder.compile(checkpointer=checkpointer, store=store)
```

The store can also be accessed with `langgraph.config.get_store()` from inside a
node, but explicit `Runtime[...]` parameters make dependencies and trusted context
clearer.

#### Optional semantic search

Plain `InMemoryStore()` supports exact lookup, namespace search, and metadata
filters, but not natural-language similarity. Semantic search must be configured
when the store is created:

```python
from retrievers.llm import get_embeddings

memory_store = InMemoryStore(
    index={
        "dims": 1536,
        "embed": get_embeddings(),
        "fields": ["text"],
    }
)

memory_namespace = ("users", "user-123", "memories")
memory_store.put(
    memory_namespace,
    "citation-preference",
    {"text": "The user prefers quotations with article titles.", "kind": "preference"},
)

matches = memory_store.search(
    memory_namespace,
    query="How should sources be presented?",
    filter={"kind": "preference"},
    limit=3,
)
```

The configured dimension must match the embedding model's actual output. Restrict
`fields` to text that should be embedded; embedding every field can mix identifiers
or private metadata into search. Items can opt out of indexing with `index=False`,
or select specific fields with `index=["text"]` when calling `put`.

Do not use a LangGraph store as a replacement for a governed corpus index or artifact
repository. A store is well suited to small application memories, preferences, and
cross-thread records. Deterministic corpus-derived data generally belongs in a
versioned offline build with a durable publication boundary. See the Checkpoint 5.1
README for this repository's table-artifact decision.

#### `InMemoryStore` gotchas

- All data disappears when the Python process exits. Use a database-backed store
  such as a tested PostgreSQL adapter when durability is required.
- It is process-local. Multiple workers do not automatically see the same data.
- Exact `get` and semantic `search` are different operations. Semantic search is
  disabled unless the store is initialized with an embedding index.
- Namespaces organize and scope records but do not enforce authorization by
  themselves; the application must enforce access control.
- Stable keys make updates idempotent. Random keys can create duplicate memories on
  retries or replayed nodes.
- Storing every interaction creates unbounded, stale, and contradictory memory.
  Define what is worth remembering, how it is corrected, and when it is deleted.
- A retrieved memory is untrusted context, not a system instruction. Stored prompt
  injection can persist across future sessions.
- Avoid secrets and unnecessary personal data. Store contents may appear in traces,
  debugging output, or model prompts.
- Use `aput`, `aget`, `asearch`, and `adelete` in a fully asynchronous path rather
  than blocking the event loop with synchronous calls.

Gotchas:

- `InMemorySaver` is lost when the process exits. Use a tested persistent saver when
  restart durability matters.
- Reusing a `thread_id` continues its state; use unique, stable IDs for independent
  evaluation cases to prevent cross-test contamination.
- Persistence can replay nodes after interruption. Any node with side effects must
  be idempotent or use a durable task pattern.
- Checkpoints can grow indefinitely. Define retention and privacy policies.
- Changing the state schema or node behavior can make old checkpoints incompatible;
  version the graph and its state.

### Streaming and inspecting execution

```python
for update in rag_graph.stream(
    {"question": "..."},
    config={"recursion_limit": 15},
    stream_mode="updates",
):
    print(update)
```

`stream_mode="updates"` emits node updates and is useful for a progress UI or trace.
Full-state streaming can reveal internal or private fields, so do not assume an
output schema redacts everything emitted by streaming.

### Evaluating an agentic graph

Compare an agentic graph with a fixed baseline while holding questions, models,
corpus, prompts, and scoring rules constant. Record:

- answer quality and designated-source recall;
- number of retrieval attempts and LLM calls;
- route taken and termination reason;
- rewrite usefulness (did the next retrieval improve source or passage recall?);
- abstention correctness after the final attempt;
- latency, input/output tokens, and estimated cost;
- loop-limit, parser, provider, and node exceptions;
- run-to-run route and answer stability.

An agentic design is useful only when its quality or recoverability improvement is
worth the additional latency, cost, and nondeterminism.

### Agentic-graph failure modes

- A grader can incorrectly reject good evidence or accept weak evidence. Evaluate it
  separately with labeled sufficient/insufficient examples.
- Query rewriting can drift away from the original question. Preserve the original
  question and require the grader and answer node to use it.
- Repeated vector retrieval can return the same chunks. Log IDs, detect duplicates,
  and consider changing retrieval strategy rather than only wording.
- A loop can multiply cost rapidly. Cap attempts and total graph steps.
- A tool-calling agent can be less reliable than explicit conditional edges. Start
  with constrained routing and add open-ended tool choice only when required.
- A successful graph execution does not imply a correct answer. Node-level traces
  and end-to-end evaluation are both necessary.

### LangGraph primary references

- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [Graph API: state, nodes, edges, reducers, and runtime](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [Using conditional edges and loops](https://docs.langchain.com/oss/python/langgraph/use-graph-api)
- [Persistence, checkpointers, stores, and threads](https://docs.langchain.com/oss/python/langgraph/persistence)
- [`InMemoryStore` API reference](https://reference.langchain.com/python/langgraph.store/memory/InMemoryStore)
- [Workflow and agent patterns](https://docs.langchain.com/oss/python/langgraph/workflows-agents)

## 16. Repository examples

- `wikipedia_retrieval_engine/retrievers/llm.py` centralizes OpenRouter chat and
  embedding clients and keeps model calls outside ranking logic.
- `wikipedia_retrieval_engine/retrievers/vector.py` builds/loads Chroma and preserves
  article and section metadata.
- `wikipedia_retrieval_engine/retrievers/hybrid.py` demonstrates lexical/vector
  fusion; examine its normalization before comparing raw scores.
- `wikipedia_retrieval_engine/utils/ragas_eval.py` is the evaluation boundary; keep
  run metadata and exact contexts reproducible.
- `wikipedia_retrieval_engine/Capstone Checkpoint 5.1/README 5.1.md` explains how
  these primitives are being applied to an evidence-routing graph and specialized
  table-analysis branch.

## 17. Primary references

- [LangChain Learn: tutorials and conceptual guides](https://docs.langchain.com/oss/python/learn)
- [LangChain Python overview](https://docs.langchain.com/oss/python/langchain/overview)
- [Models and the standard invocation interface](https://docs.langchain.com/oss/python/langchain/models)
- [Messages](https://docs.langchain.com/oss/python/langchain/messages)
- [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [Chroma integration](https://docs.langchain.com/oss/python/integrations/vectorstores/chroma)
- [Embedding integrations](https://docs.langchain.com/oss/python/integrations/embeddings)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph workflows and agents](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangChain Python reference](https://reference.langchain.com/python/)

Last reviewed against the official documentation: 2026-09-20.
