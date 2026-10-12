"""Vector (semantic) retrieval with a Chroma index. (Checkpoint 2)

Every passage is embedded once and stored in a Chroma index under
RAG_WORK_DIR/indexes/<name>/. A question is embedded the same way, and Chroma returns
the passages whose embeddings are closest. This finds paraphrases that keyword search
misses, but can miss exact names and numbers that keyword search finds.

Chroma reports a cosine DISTANCE (0 = identical, lower is better). This retriever
returns 1 - distance, the cosine similarity, so that here too higher is better.

The index records how the corpus was read (folder, passage size, file limit), so that
keyword search and evaluation can rebuild exactly the same passages later.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma

from ragkit import config
from ragkit.corpus import Document
from ragkit.embeddings import count_tokens, make_embeddings
from ragkit.pipelines.base import LLMCall
from ragkit.retrievers.base import BaseRetriever, Hit

INDEX_INFO = "ragkit_index.json"
COLLECTION = "passages"


class VectorRetriever(BaseRetriever):
    name = "vector"

    def __init__(self, index_name: str, embeddings: Any = None, folder: Path | None = None):
        super().__init__()
        self.index_name = index_name
        self.path = (folder or config.indexes_dir()) / index_name
        self.embeddings = embeddings or make_embeddings()
        self.store = Chroma(
            collection_name=COLLECTION,
            embedding_function=self.embeddings,
            persist_directory=str(self.path),
            collection_metadata={"hnsw:space": "cosine"},
        )

    def settings(self) -> dict[str, Any]:
        return {"name": self.name, "index": self.index_name}

    def count(self) -> int:
        return self.store._collection.count()

    def retrieve(self, query: str, k: int = 5) -> list[Hit]:
        started = time.perf_counter()
        results = self.store.similarity_search_with_score(query, k=k)
        self.calls.append(
            LLMCall(
                role="embedding",
                model=str(getattr(self.embeddings, "model", "unknown")),
                input_tokens=count_tokens([query]),
                output_tokens=0,
                latency_s=round(time.perf_counter() - started, 3),
            )
        )
        hits = []
        for found, distance in results:
            metadata = dict(found.metadata)
            doc_id = metadata.pop("doc_id", found.id)
            hits.append(Hit(Document(doc_id, found.page_content, metadata), 1.0 - float(distance)))
        return hits

    def add(self, documents: list[Document], batch_size: int = 64, progress: Callable[[str], None] = print) -> None:
        """Embed and store ``documents``, skipping any already in the index (so an
        interrupted build continues where it stopped)."""
        existing = set(self.store._collection.get(include=[])["ids"])
        todo = [document for document in documents if document.id not in existing]
        if existing:
            progress(f"  {len(existing):,} passages already indexed; {len(todo):,} to add")
        for start in range(0, len(todo), batch_size):
            batch = todo[start : start + batch_size]
            self.store.add_texts(
                texts=[document.text for document in batch],
                metadatas=[_storable_metadata(document) for document in batch],
                ids=[document.id for document in batch],
            )
            progress(f"  embedded {start + len(batch):,}/{len(todo):,}")

    @classmethod
    def build(
        cls,
        index_name: str,
        documents: list[Document],
        corpus_settings: dict[str, Any],
        embeddings: Any = None,
        folder: Path | None = None,
        progress: Callable[[str], None] = print,
    ) -> VectorRetriever:
        """Create (or finish) an index and record how its passages were made."""
        retriever = cls(index_name, embeddings, folder)
        retriever.add(documents, progress=progress)
        info = {
            "name": index_name,
            "corpus": corpus_settings,
            "passages": retriever.count(),
            "embedding_model": str(getattr(retriever.embeddings, "model", "unknown")),
            "built": datetime.now().isoformat(timespec="seconds"),
        }
        (retriever.path / INDEX_INFO).write_text(json.dumps(info, indent=2), encoding="utf-8")
        return retriever

    @staticmethod
    def info(index_name: str, folder: Path | None = None) -> dict[str, Any] | None:
        """How an index was built, or None when it does not exist (or was never finished)."""
        path = (folder or config.indexes_dir()) / index_name / INDEX_INFO
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    @staticmethod
    def list_indexes(scenario: str | None = None, folder: Path | None = None) -> list[dict[str, Any]]:
        """Finished indexes, newest first; only ``scenario``'s when given."""
        found = []
        for info_file in (folder or config.indexes_dir()).glob(f"*/{INDEX_INFO}"):
            info = json.loads(info_file.read_text(encoding="utf-8"))
            if scenario is None or info.get("corpus", {}).get("scenario") == scenario:
                found.append(info)
        return sorted(found, key=lambda info: info.get("built", ""), reverse=True)


def _storable_metadata(document: Document) -> dict[str, Any]:
    """Chroma stores only plain values (text, numbers, true/false), so lists are dropped."""
    kept = {key: value for key, value in document.metadata.items() if isinstance(value, (str, int, float, bool))}
    kept["doc_id"] = document.id
    return kept
