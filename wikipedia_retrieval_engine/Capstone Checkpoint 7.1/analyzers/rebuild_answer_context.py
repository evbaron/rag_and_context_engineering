"""Rebuild the exact context a saved answer was given, offline and at no API cost.

Checkpoint 7.1 measures a guardrail against answers that were already produced, so the
guardrail must see the same string the answer model saw. Three facts make that
reconstruction possible without re-running anything:

- the experiment CSV's ``evidence_ids`` column records the answer evidence in order,
  with a whole article appearing as ``whole_article:<source>``;
- the evidence log for the same question holds each section or table snippet's content;
- the markdown store holds every article's full text.

The reconstruction is self-verifying. ``survivor_6_1.py`` records
``context_characters = len(context)``, so a rebuilt context of the same length is the
same context. ``--self-check`` rebuilds every row of the recorded 6.1 runs and fails
unless all of them match, the control ``answer_replay_starter.py`` already applies to the
5.1 replay.

Two formatting-critical functions are imported from the live code rather than copied, so
this harness cannot drift from the code that produced the runs: the 5.1 harness's
``format_section_evidence`` (with its ``_CONTEXT_SEPARATOR``) and 6.1's
``evidence_status_notice``.

Usage:

    python "Capstone Checkpoint 7.1/rebuild_answer_context.py" --self-check
    python "Capstone Checkpoint 7.1/rebuild_answer_context.py" --run dazzling_minsky --question VAL22 --show
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent     # .../Capstone Checkpoint 7.1/analyzers
ENGINE = HERE.parent.parent               # .../wikipedia_retrieval_engine
REPO = ENGINE.parent                      # .../rag_and_context_engineering
CHECKPOINT_6_1 = ENGINE / "Capstone Checkpoint 6.1"

# The live code this harness must not duplicate.
for path in (str(REPO.parent), str(CHECKPOINT_6_1)):
    if path not in sys.path:
        sys.path.insert(0, path)

from survivor_agent import load_harness_5_1  # noqa: E402
from wikipedia_retrieval_engine.wiki_agents.agentic_models import (  # noqa: E402
    EvidenceAssessment,
    EvidenceItem,
)
from wikipedia_retrieval_engine.wiki_agents.answer_context import (  # noqa: E402
    WHOLE_ARTICLE_STAGE,
    evidence_status_notice,
)

DEFAULT_GT_SET = "wikipedia_GT_validation_set"
MARKDOWN_STORE = ENGINE / "retrievers" / "db" / "article_text" / "wikipedia_markdown"

# The recorded 6.1 survivor runs on gpt-5.4-mini, the "before" for 7.1.
SURVIVOR_6_1_MINI_RUNS = ("dazzling_minsky", "nifty_mccarthy", "angry_babbage")


@dataclass
class RebuiltAnswer:
    """One saved question-run with its answer context reconstructed."""

    question_id: str
    run: str
    question: str
    answer: str
    score: str
    context: str
    evidence: list[EvidenceItem]
    notice: str | None
    recorded_characters: int
    whole_articles: list[str]
    tables_flagged: bool
    final_state: dict[str, Any]
    unresolved_evidence_ids: list[str] = field(default_factory=list)

    @property
    def path(self) -> str:
        """``"text"`` when whole articles were sent, ``"table"`` otherwise."""

        return "text" if self.whole_articles else "table"

    @property
    def matches_recording(self) -> bool:
        return len(self.context) == self.recorded_characters


def _markdown_text(source: str, store_dir: Path = MARKDOWN_STORE) -> str | None:
    """An article's full markdown, or None when the store does not hold it."""

    path = store_dir / f"{source}.md"
    return path.read_text(encoding="utf-8") if path.is_file() else None


def _whole_article_item(source: str, text: str) -> EvidenceItem:
    """The whole-article evidence item, as ``answer_context.whole_article_item`` builds it."""

    return EvidenceItem(
        evidence_id=f"{WHOLE_ARTICLE_STAGE}:{source}",
        source_article=source,
        content=text,
        section_path=["(whole article)"],
        metadata={"retrieval_stage": WHOLE_ARTICLE_STAGE},
    )


def _state_from_log(record: dict[str, Any]) -> dict[str, Any]:
    """The logged ``final_state`` with its evidence and assessment back as models."""

    state = dict(record["final_state"])
    state["evidence"] = [EvidenceItem.model_validate(item) for item in state.get("evidence", [])]
    if state.get("assessment") is not None:
        state["assessment"] = EvidenceAssessment.model_validate(state["assessment"])
    return state


def _log_records(log_dir: Path) -> dict[int, dict[str, Any]]:
    """Every ``*.evidence.json`` in one run's log directory, keyed by question number."""

    records = {}
    for path in sorted(log_dir.glob("*.evidence.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        records[record["question_number"]] = record
    return records


def _snippet_ids(row: dict[str, str]) -> set[str]:
    """The row's answer-evidence ids that must come from the log, not the markdown store."""

    return {
        part.strip()
        for part in row["evidence_ids"].split(";")
        if part.strip() and not part.strip().startswith(f"{WHOLE_ARTICLE_STAGE}:")
    }


def find_log_dir(rows: list[dict[str, str]], logs_root: Path) -> tuple[Path, int]:
    """The log directory produced by the run these CSV rows come from.

    The link is not recorded anywhere and question text does not identify it: every run
    answers the same GT set, so each run's log matches every row's question. What is
    run-specific is the evidence itself, so a candidate scores a row only when the
    question matches *and* every snippet id the row's answer used is present in that
    record's evidence. A log from the same run scores every row; any other scores fewer.
    """

    best: tuple[int, Path | None] = (-1, None)
    for candidate in sorted(p for p in logs_root.iterdir() if p.is_dir()):
        records = _log_records(candidate)
        matches = 0
        for number, row in enumerate(rows, start=1):
            record = records.get(number)
            if record is None or record["question"].strip() != row["question"].strip():
                continue
            logged = {item["evidence_id"] for item in record["final_state"].get("evidence", [])}
            if _snippet_ids(row) <= logged:
                matches += 1
        if matches > best[0]:
            best = (matches, candidate)
    if best[1] is None:
        raise FileNotFoundError(f"No log directories under {logs_root}")
    return best[1], best[0]


def rebuild_row(
    row: dict[str, str],
    record: dict[str, Any],
    store_dir: Path = MARKDOWN_STORE,
    run: str | None = None,
) -> RebuiltAnswer:
    """Reconstruct one question-run's answer context from its CSV row and log record."""

    harness = load_harness_5_1()
    state = _state_from_log(record)
    snippets = {item.evidence_id: item for item in state["evidence"]}

    evidence: list[EvidenceItem] = []
    unresolved: list[str] = []
    for evidence_id in (part.strip() for part in row["evidence_ids"].split(";")):
        if not evidence_id:
            continue
        if evidence_id.startswith(f"{WHOLE_ARTICLE_STAGE}:"):
            source = evidence_id.split(":", 1)[1]
            text = _markdown_text(source, store_dir)
            if text is None:
                unresolved.append(evidence_id)
                continue
            evidence.append(_whole_article_item(source, text))
        elif evidence_id in snippets:
            evidence.append(snippets[evidence_id])
        else:
            unresolved.append(evidence_id)

    context = harness.format_section_evidence(evidence)
    notice = evidence_status_notice(state)
    if context.strip() and notice:
        context = f"{context}{harness._CONTEXT_SEPARATOR}[Evidence status]\n{notice}"

    return RebuiltAnswer(
        question_id=row["question_id"],
        run=run or row["experiment_name"],
        question=row["question"],
        answer=row["response"],
        score=row["score"],
        context=context,
        evidence=evidence,
        notice=notice,
        recorded_characters=int(row["context_characters"]),
        whole_articles=[a.strip() for a in row["whole_articles_sent"].split(";") if a.strip()],
        tables_flagged=row["tables_flagged"].strip().lower() == "true",
        final_state=state,
        unresolved_evidence_ids=unresolved,
    )


def rebuild_experiment(
    run: str,
    *,
    gt_set: str = DEFAULT_GT_SET,
    checkpoint_dir: Path = CHECKPOINT_6_1,
    store_dir: Path = MARKDOWN_STORE,
) -> list[RebuiltAnswer]:
    """Every question-run of one recorded experiment, with its context rebuilt."""

    csv_path = checkpoint_dir / "cost_tests" / gt_set / "experiments" / f"{run}.csv"
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    log_dir, matches = find_log_dir(rows, checkpoint_dir / "logs" / "cost_tests")
    if matches < len(rows):
        raise RuntimeError(
            f"{run}: best log directory {log_dir.name} matches only {matches}/{len(rows)} "
            "questions by text; the run and its log may not correspond"
        )
    records = _log_records(log_dir)
    return [
        rebuild_row(row, records[number], store_dir, run=run)
        for number, row in enumerate(rows, start=1)
    ]


def rebuild_runs(runs: Iterable[str] = SURVIVOR_6_1_MINI_RUNS, **kwargs: Any) -> list[RebuiltAnswer]:
    """Several experiments' question-runs in one list."""

    return [rebuilt for run in runs for rebuilt in rebuild_experiment(run, **kwargs)]


def self_check(runs: Iterable[str] = SURVIVOR_6_1_MINI_RUNS) -> int:
    """Rebuild the recorded runs and report whether every context matches its recording."""

    rebuilt = rebuild_runs(runs)
    mismatched = [r for r in rebuilt if not r.matches_recording]
    unresolved = [r for r in rebuilt if r.unresolved_evidence_ids]

    print(f"Rebuilt {len(rebuilt)} question-runs from {', '.join(runs)}.")
    by_path: dict[str, int] = {}
    for r in rebuilt:
        by_path[r.path] = by_path.get(r.path, 0) + 1
    print(f"  paths: " + ", ".join(f"{name}={count}" for name, count in sorted(by_path.items())))
    print(f"  with an [Evidence status] notice: {sum(1 for r in rebuilt if r.notice)}")

    for r in unresolved:
        print(f"  UNRESOLVED EVIDENCE {r.run}/{r.question_id}: {r.unresolved_evidence_ids}")
    for r in mismatched:
        delta = r.recorded_characters - len(r.context)
        print(
            f"  MISMATCH {r.run}/{r.question_id}: rebuilt={len(r.context)} "
            f"recorded={r.recorded_characters} delta={delta:+d}"
        )

    if mismatched or unresolved:
        print(f"\nFAILED: {len(mismatched)} mismatched, {len(unresolved)} with unresolved evidence.")
        return 1
    print(f"\nPASSED: {len(rebuilt)}/{len(rebuilt)} rebuilt contexts match context_characters.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--self-check", action="store_true", help="rebuild the recorded 6.1 runs and verify every context")
    parser.add_argument("--run", action="append", dest="runs", help="experiment name; repeatable (default: the three 6.1 mini runs)")
    parser.add_argument("--question", help="restrict --show to one question id")
    parser.add_argument("--show", action="store_true", help="print a summary line per question-run")
    parser.add_argument("--gt-set", default=DEFAULT_GT_SET)
    args = parser.parse_args()

    runs = tuple(args.runs) if args.runs else SURVIVOR_6_1_MINI_RUNS

    if args.self_check or not args.show:
        return self_check(runs)

    for rebuilt in rebuild_runs(runs, gt_set=args.gt_set):
        if args.question and rebuilt.question_id != args.question:
            continue
        flag = "ok" if rebuilt.matches_recording else "MISMATCH"
        print(
            f"{rebuilt.question_id:6s} {rebuilt.run:16s} {rebuilt.path:5s} "
            f"score={rebuilt.score:8s} chars={len(rebuilt.context):7d} ({flag}) "
            f"notice={'yes' if rebuilt.notice else 'no':3s} "
            f"evidence={len(rebuilt.evidence):3d} whole={len(rebuilt.whole_articles)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
