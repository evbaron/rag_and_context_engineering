"""Run the Checkpoint 6.1 cost-and-quality harness against the Checkpoint 7.1 agent.

The dataset, the RAGAS judge, the telemetry and the price table all come from
`Capstone Checkpoint 6.1/cost_test_starter.py`, imported rather than copied, so a 7.1 run
is comparable with the recorded 6.1 runs question for question. This entry point only
fixes `--survivor final` and puts 7.1's results, telemetry and AgentState logs under
Checkpoint 7.1 instead of Checkpoint 6.1.

History is OFF here, as in every cost run: this measures quality, tokens, cost and
latency on the validation set. The multi-turn attack behaviour is measured by
`security_test_final.py`, where history is ON.

The comparison already on disk, from the same harness and the same judge
(`Capstone Checkpoint 6.1/cost_tests/wikipedia_GT_validation_set/experiments/`):

    quirky_adleman    5.1 survivor   quality 0.860
    dazzling_minsky   6.1 survivor   quality 0.880
    nifty_mccarthy    6.1 survivor   quality 0.800
    angry_babbage     6.1 survivor   quality 0.900   -> 6.1 mean 0.860, $0.0296/question

    python "Capstone Checkpoint 7.1/cost_test_final.py" --question-id VAL22   # one question
    python "Capstone Checkpoint 7.1/cost_test_final.py"                       # full validation set
    python "Capstone Checkpoint 7.1/cost_test_final.py" --self-check          # offline
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
CHECKPOINT_6_1 = ENGINE / "Capstone Checkpoint 6.1"

for path in (str(ENGINE.parent.parent), str(CHECKPOINT_6_1), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

from cost_test_starter import VALIDATION_PATH  # noqa: E402
from cost_test_starter import main as run_cost_test  # noqa: E402

OUTPUT_ROOT = HERE / "cost_tests"


def _flag_value(arguments: list[str], flag: str) -> str | None:
    if flag not in arguments:
        return None
    index = arguments.index(flag)
    return arguments[index + 1] if index + 1 < len(arguments) else None


def main(argv: list[str] | None = None) -> int:
    """Forward to the 6.1 harness with 7.1's survivor and 7.1's output directory."""

    arguments = list(argv if argv is not None else sys.argv[1:])

    given = _flag_value(arguments, "--survivor")
    if given is not None and given != "final":
        raise SystemExit(
            f"This entry point runs the 7.1 agent; --survivor {given!r} is not its job.\n"
            f"The 5.1 and 6.1 runs are already on disk under\n"
            f"  {CHECKPOINT_6_1 / 'cost_tests'}\n"
            f"and for a fresh run of either arm use the 6.1 starter directly."
        )
    if given is None:
        arguments += ["--survivor", "final"]

    if "--output-dir" not in arguments:
        # The 6.1 default is <checkpoint>/cost_tests/<gt-set stem>; keep that shape so a
        # 7.1 run is laid out like the runs it is compared with.
        gt_set = _flag_value(arguments, "--gt-set")
        stem = Path(gt_set).stem if gt_set else VALIDATION_PATH.stem
        arguments += ["--output-dir", str(OUTPUT_ROOT / stem)]

    asyncio.run(run_cost_test(arguments))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
