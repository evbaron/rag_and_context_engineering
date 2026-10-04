"""Replay the 7.1 guardrail over the recorded 6.1 answers, offline and at no API cost.

Every input is already on disk: `rebuild_answer_context` reconstructs the exact evidence
each saved answer was given (verified against the recorded `context_characters`), and the
experiment CSVs hold the answer and the judge's verdict. So the guardrail's trigger rate
and the quality cost of each policy can be measured before any paid run.

What the replay can and cannot say:

- **Trigger rate** is exact. The check is deterministic and sees the same evidence.
- **`off` and `surface` quality** are the recorded quality: neither changes the answer's
  factual content, so the judge's verdict carries over. `surface` puts a `[QUARANTINED]` notice before
  the answer, and whether a judge penalises the notice is *not* measured here -- 6.1 saw hedged answers
  lose marks, so this is an upper bound for `surface`.
- **`withhold` quality** assumes a withheld answer scores `fail`, which it must: the
  canned reply contains no answer.

Usage:

    python "Capstone Checkpoint 7.1/replay_grounding.py"
    python "Capstone Checkpoint 7.1/replay_grounding.py" --show-flags
"""

from __future__ import annotations

import argparse
import collections
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent    # .../Capstone Checkpoint 7.1/analyzers
ENGINE = HERE.parent.parent               # .../wikipedia_retrieval_engine
for _path in (str(ENGINE.parent), str(HERE)):  # the package root, then this folder
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wikipedia_retrieval_engine.wiki_agents.answer_guard import GROUNDING_POLICIES, guard_answer  # noqa: E402
from rebuild_answer_context import SURVIVOR_6_1_MINI_RUNS, rebuild_runs  # noqa: E402

SCORE_VALUE = {"pass": 1.0, "partial": 0.5, "fail": 0.0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--show-flags", action="store_true", help="print every flagged answer")
    parser.add_argument("--run", action="append", dest="runs")
    args = parser.parse_args()
    runs = tuple(args.runs) if args.runs else SURVIVOR_6_1_MINI_RUNS

    rebuilt = rebuild_runs(runs)
    unverified = [r for r in rebuilt if not r.matches_recording]
    if unverified:
        print(f"REFUSING to report: {len(unverified)} rebuilt contexts do not match context_characters.")
        return 1

    guarded = [(r, guard_answer(r.answer, r.evidence, policy="off")) for r in rebuilt]

    print(f"Replayed {len(rebuilt)} question-runs from {', '.join(runs)} "
          f"({len(rebuilt)}/{len(rebuilt)} contexts verified).")
    print()

    # Trigger rate, by path and by recorded score.
    print("GUARDRAIL TRIGGER RATE")
    for key, label in (("path", "path"), ("score", "recorded score")):
        counts: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
        for r, g in guarded:
            bucket = r.path if key == "path" else r.score
            counts[bucket][0] += 1
            counts[bucket][1] += (not g.result.grounded)
        print(f"  by {label}:")
        for bucket, (n, flagged) in sorted(counts.items()):
            print(f"    {bucket:8s} rows={n:3d}  flagged={flagged:3d} ({flagged / n:.0%})")
    total = sum(1 for _ in guarded)
    flagged_total = sum(1 for _, g in guarded if not g.result.grounded)
    print(f"  overall: {flagged_total}/{total} ({flagged_total / total:.0%})")
    print()

    # Quality under each policy, per run and overall.
    print("VALIDATION QUALITY BY POLICY  (pass=1.0, partial=0.5, fail=0.0)")
    header = f"  {'run':16s}" + "".join(f"{p:>12s}" for p in GROUNDING_POLICIES)
    print(header)
    means: dict[str, list[float]] = {p: [] for p in GROUNDING_POLICIES}
    for run in runs:
        rows = [(r, g) for r, g in guarded if r.run == run]
        line = f"  {run:16s}"
        for policy in GROUNDING_POLICIES:
            quality = sum(
                0.0 if (policy == "withhold" and not g.result.grounded) else SCORE_VALUE[r.score]
                for r, g in rows
            ) / len(rows)
            means[policy].append(quality)
            line += f"{quality:12.3f}"
        print(line)
    print("  " + "-" * (16 + 12 * len(GROUNDING_POLICIES)))
    line = f"  {'MEAN':16s}"
    for policy in GROUNDING_POLICIES:
        line += f"{sum(means[policy]) / len(means[policy]):12.3f}"
    print(line)
    print()
    print("  'off' and 'surface' carry the recorded verdict: neither alters the answer's")
    print("  factual content. 'surface' adds a [QUARANTINED] notice whose judged cost is NOT measured")
    print("  here, so its figure is an upper bound. 'withhold' scores a withheld answer as")
    print("  fail, which it must: the canned reply contains no answer.")

    if args.show_flags:
        print()
        print("FLAGGED ANSWERS")
        for r, g in guarded:
            if g.result.grounded:
                continue
            print(f"  {r.question_id:6s} {r.run:16s} {r.path:5s} score={r.score:8s} "
                  f"spans={len(g.result.failures)}")
            for span in g.result.ungrounded_quotations:
                print(f"      QUOTE  {span[:120]!r}")
            for span in g.result.ungrounded_entities[:5]:
                print(f"      ENTITY {span[:70]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
