"""The baseline: the configuration that every later idea has to beat. (Checkpoint 3)

At the end of Checkpoint 3, the best configuration (retriever, passages per question,
chat model) is saved to RAG_WORK_DIR/baseline.json, with a note on the evidence that
chose it. Checkpoints 4 and 5 run every new idea against the baseline on the same
questions; when an idea wins on both the gt and the validation questions, it becomes
the new baseline.

    python samples/cp3_save_baseline.py --retriever hybrid --k 5 --note "best recall and quality"
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ragkit import config
from ragkit.corpus import Document
from ragkit.pipelines.rag import RAGPipeline
from ragkit.retrievers.factory import KINDS, make_retriever, open_documents

BASELINE_FILE = "baseline.json"


def save_baseline(
    retriever: str,
    k: int,
    *,
    index: str | None = None,
    model: str | None = None,
    weight_keyword: float = 0.5,
    note: str = "",
) -> Path:
    if retriever not in KINDS:
        raise ValueError(f"retriever must be one of: {', '.join(KINDS)}")
    baseline = {
        "retriever": retriever,
        "k": k,
        "index": index,
        "model": model or config.model(),
        "weight_keyword": weight_keyword,
        "scenario": config.scenario(),
        "note": note,
        "chosen": datetime.now().isoformat(timespec="seconds"),
    }
    path = config.work_dir() / BASELINE_FILE
    path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    return path


def load_baseline() -> dict[str, Any]:
    path = config.work_dir() / BASELINE_FILE
    if not path.is_file():
        raise config.SetupError(
            "No baseline chosen yet. After comparing runs in Checkpoint 3, save the best one, for example: "
            "python samples/cp3_save_baseline.py --retriever hybrid --k 5"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def open_baseline() -> tuple[RAGPipeline, list[Document], dict[str, Any]]:
    """The baseline pipeline, the passages it searches, and the saved settings."""
    baseline = load_baseline()
    documents, index_name = open_documents(baseline.get("index"))
    retriever = make_retriever(baseline["retriever"], documents, index_name, weight_keyword=baseline.get("weight_keyword", 0.5))
    pipeline = RAGPipeline(retriever, k=baseline["k"], model=baseline.get("model"))
    return pipeline, documents, baseline
