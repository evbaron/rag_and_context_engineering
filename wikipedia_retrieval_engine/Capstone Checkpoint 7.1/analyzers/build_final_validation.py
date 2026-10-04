"""Assemble the final validation comparison: 5.1, 6.1, and 7.1 survivors, three runs each.

The runs live where they were recorded; this script copies them into
``Capstone Checkpoint 7.1/final_validation/runs/`` (``experiments/`` and ``telemetry/``, the
layout both analyzers read) and sets each copy's ``experiment_name`` to one label per
configuration, so the original analyzer, which groups runs by experiment name, shows one
group per survivor. Only the copies change; the recorded files are untouched. File times
are preserved, so run order still follows when each run was recorded.

Selection (2026-10-04):

- 5.1 survivor: ``quirky_adleman`` (the one 5.1 validation run with cost telemetry), and the
  two most recent of the four 2026-09-23 runs, ``eager_rossum`` and ``objective_hopper``;
- 6.1 survivor: its three ``gpt-5.4-mini`` runs;
- 7.1Final Survivor: the three Router B validation runs recorded in
  ``cost_efficiency/wikipedia_GT_validation_set/``. The mini-only 7.1 baseline is omitted:
  it reproduced 6.1's validation quality and adds no survivor step to the final lineage.

Writes ``final_validation/provenance.csv`` (copy, source, original name, label, rows,
quality, telemetry). No API calls.

    python "Capstone Checkpoint 7.1/analyzers/build_final_validation.py"
"""

from __future__ import annotations

import csv
import os
import shutil
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKPOINT_7_1 = HERE.parent
ENGINE = CHECKPOINT_7_1.parent
OUT = CHECKPOINT_7_1 / "final_validation"
RUNS = OUT / "runs"

V51 = ENGINE / "Capstone Checkpoint 5.1" / "ragas_validation_GT_5.1"
V61 = ENGINE / "Capstone Checkpoint 6.1" / "cost_tests" / "wikipedia_GT_validation_set"
V71 = CHECKPOINT_7_1 / "cost_efficiency" / "wikipedia_GT_validation_set"

SELECTION = [
    ("5.1 survivor", V61, "quirky_adleman"),
    ("5.1 survivor", V51, "eager_rossum"),
    ("5.1 survivor", V51, "objective_hopper"),
    ("6.1 survivor", V61, "dazzling_minsky"),
    ("6.1 survivor", V61, "nifty_mccarthy"),
    ("6.1 survivor", V61, "angry_babbage"),
    ("7.1Final Survivor", V71, "xenodochial_tarjan"),
    ("7.1Final Survivor", V71, "thirsty_stallman"),
    ("7.1Final Survivor", V71, "sweet_dijkstra"),
]
SCORE = {"pass": 1.0, "partial": 0.5, "fail": 0.0}


def copy_run(label: str, root: Path, run: str) -> dict[str, object]:
    source = root / "experiments" / f"{run}.csv"
    target = RUNS / "experiments" / f"{run}.csv"
    with source.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    original = rows[0].get("experiment_name", "") if rows else ""
    for row in rows:
        row["experiment_name"] = label
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    stat = source.stat()
    os.utime(target, (stat.st_atime, stat.st_mtime))

    telemetry = sorted((root / "telemetry").glob(f"{run}__*.csv")) if (root / "telemetry").is_dir() else []
    for path in telemetry:
        shutil.copy2(path, RUNS / "telemetry" / path.name)
    return {
        "copy": str(target.relative_to(OUT)),
        "source": str(source.relative_to(ENGINE)),
        "original_experiment_name": original,
        "label": label,
        "rows": len(rows),
        "quality": round(sum(SCORE[row["score"]] for row in rows) / len(rows), 3),
        "telemetry_files": len(telemetry),
        "recorded": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
    }


def main() -> int:
    # This folder is a generated comparison workspace. Rebuild it from the explicit
    # selection so configurations removed above cannot survive as stale CSVs.
    if RUNS.exists():
        shutil.rmtree(RUNS)
    for folder in (RUNS / "experiments", RUNS / "telemetry"):
        folder.mkdir(parents=True, exist_ok=True)
    records = [copy_run(*entry) for entry in SELECTION]
    with (OUT / "provenance.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    for record in records:
        print(f"{record['label']:18s} {Path(record['copy']).stem:20s} q={record['quality']:.3f} rows={record['rows']} "
              f"telemetry={record['telemetry_files']} recorded {record['recorded']} (was {record['original_experiment_name']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
