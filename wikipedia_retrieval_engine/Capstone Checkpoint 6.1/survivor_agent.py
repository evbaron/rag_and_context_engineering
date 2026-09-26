"""Shared loader for the Checkpoint 5.1 survivor agent used by the 6.1 starters.

The survivor configuration (initial retriever, repeated retrievers, k values,
budgets) is read from the 5.1 harness module itself, and the graph is assembled
with the same calls as the 5.1 harness ``main()``. The 6.1 starters therefore run
exactly the configuration recorded in README 5.1 without copying its constants,
and nothing in Checkpoint 5.1 is modified.

The only difference from a 5.1 run is where the per-question AgentState logs go:
``Capstone Checkpoint 6.1/logs/<log_subdir>/<run timestamp>/``.
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
PACKAGE_ROOT = ENGINE.parent
for _path in (PACKAGE_ROOT, ENGINE):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

HARNESS_5_1_PATH = (
    ENGINE / "Capstone Checkpoint 5.1" / "capstone_checkpoint_5_1_agent_rag_starter.py"
)
LOG_ROOT = HERE / "logs"
GT_PATH = ENGINE / "GT" / "wikipedia_GT.csv"
VALIDATION_PATH = ENGINE / "GT" / "wikipedia_GT_validation_set.csv"
CORPUS_DIR = ENGINE / "Wikipedia Library"

_HARNESS_MODULE_NAME = "checkpoint_5_1_harness"


def load_harness_5_1() -> ModuleType:
    """Import the 5.1 harness by path; its ``main()`` is not executed."""

    if _HARNESS_MODULE_NAME in sys.modules:
        return sys.modules[_HARNESS_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_HARNESS_MODULE_NAME, HARNESS_5_1_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load the 5.1 harness from {HARNESS_5_1_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_HARNESS_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


@dataclass
class SurvivorAgent:
    """The compiled 5.1 graph plus the objects a 6.1 starter needs around it."""

    harness: ModuleType  # the 5.1 harness module (constants, formatting, experiment)
    graph: Any  # CompiledStateGraph
    agent_llm: Any  # the one chat client shared by every agent role, as in 5.1
    run_logger: Any  # AgentRunLogger writing under Capstone Checkpoint 6.1/logs/


def build_survivor_agent(log_subdir: str) -> SurvivorAgent:
    """Build the survivor graph exactly as the 5.1 harness ``main()`` does."""

    h = load_harness_5_1()
    retriever = h.VectorRetriever.for_section_index(
        top_k=h.INITIAL_ARTICLE_TOP_K,
        label=f"section_vector_articles_k{h.INITIAL_ARTICLE_TOP_K}",
    )
    agent_llm = h.make_llm()
    multistep_retriever = h.MultiStepRetriever(
        llm=agent_llm,
        chroma_db_name=h.DEFAULT_SECTION_CHROMA_DB_NAME,
        top_k=h.MULTISTEP_HITS_PER_REQUEST,
        label="targeted_multistep_sections",
    )
    relationship_store = h.build_or_load_markdown_store()
    wiki_graph = h.build_or_load_graph(relationship_store)
    table_store = h.TableArtifactStore.open()
    run_logger = h.AgentRunLogger(log_root=LOG_ROOT / log_subdir)
    graph = h.build_retrieval_benchmark_graph(
        retriever,
        multistep_retriever,
        wiki_graph,
        agent_llm,
        run_logger,
        markdown_store=relationship_store,
        table_store=table_store,
        initial_retriever=h.INITIAL_RETRIEVER,
        repeated_retrievers=h.REPEATED_RETRIEVERS,
        initial_article_top_k=h.INITIAL_ARTICLE_TOP_K,
        initial_subquery_top_k=h.INITIAL_SUBQUERY_TOP_K,
        initial_max_candidates=h.INITIAL_MAX_CANDIDATES,
        sections_per_selected_article=h.SECTIONS_PER_SELECTED_ARTICLE,
        graph_params=h.GRAPH_PARAMS,
        sections_per_neighbor=h.SECTIONS_PER_GRAPH_NEIGHBOR,
        max_graph_sections=h.MAX_GRAPH_SECTIONS,
        multistep_hits_per_request=h.MULTISTEP_HITS_PER_REQUEST,
        max_table_rounds=h.MAX_TABLE_ROUNDS,
        max_table_requests_per_round=h.MAX_TABLE_REQUESTS_PER_ROUND,
    )
    return SurvivorAgent(harness=h, graph=graph, agent_llm=agent_llm, run_logger=run_logger)


def describe_survivor(h: ModuleType) -> str:
    """One-block summary of the survivor configuration for run headers."""

    return (
        f"  initial retriever={h.INITIAL_RETRIEVER}\n"
        f"  repeated retrievers={' -> '.join(h.REPEATED_RETRIEVERS)}\n"
        f"  initial article k={h.INITIAL_ARTICLE_TOP_K}\n"
        f"  sections per selected article={h.SECTIONS_PER_SELECTED_ARTICLE}\n"
        f"  table rounds={h.MAX_TABLE_ROUNDS}, requests per round={h.MAX_TABLE_REQUESTS_PER_ROUND}\n"
        f"  model={h.LLM_MODEL} (every agent role), judge={h.JUDGE_MODEL}"
    )
