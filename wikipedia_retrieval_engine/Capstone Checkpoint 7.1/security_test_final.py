"""Run the Checkpoint 6.1 security scenarios against the Checkpoint 7.1 agent.

The scenarios, the plant payloads, the detectors, the outcome labels and the judge all
come from `Capstone Checkpoint 6.1/security_test_starter.py`, imported rather than copied.
That is the point: a comparison against the recorded 5.1 runs is only meaningful if the
attacks and the scoring are byte-for-byte the same. Copying them would let them drift.

What this adds is ownership. The 6.1 starter writes results and AgentState logs under
Checkpoint 6.1, which is right for its own runs and wrong for these; this entry point
puts 7.1's artefacts under Checkpoint 7.1 and fixes `--survivor final`, so running the
7.1 security test never means working inside the 6.1 folder.

The baseline needs no run: the 5.1 security runs are already on disk under
`Capstone Checkpoint 6.1/security_tests/` (12 runs, 130 turns, 2026-09-26), and 5.1 is
the configuration with no security work in it.

One run reports both sides of the comparison. `outcome` is classified from the answer the
model drafted, before the guardrail acted, so it says what the agent would have delivered
without the grounding check; `grounding_acted` says whether the check then intervened.
A separate `--grounding off` run is not needed.

    # plumbing check, one conversation
    python "Capstone Checkpoint 7.1/security_test_final.py" --scenario plant_buried --repeats 1

    # the full comparison against the recorded 5.1 runs
    python "Capstone Checkpoint 7.1/security_test_final.py" --scenario all --repeats 3

    # offline, no API key
    python "Capstone Checkpoint 7.1/security_test_final.py" --self-check
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parent
CHECKPOINT_6_1 = ENGINE / "Capstone Checkpoint 6.1"

for path in (str(ENGINE.parent.parent), str(CHECKPOINT_6_1), str(HERE)):
    if path not in sys.path:
        sys.path.insert(0, path)

from security_test_starter import main as run_security_tests  # noqa: E402

OUTPUT_ROOT = HERE / "security_tests"


def main(argv: list[str] | None = None) -> int:
    """Forward to the 6.1 runner with 7.1's survivor and 7.1's output directory."""

    arguments = list(argv if argv is not None else sys.argv[1:])

    if "--survivor" in arguments:
        index = arguments.index("--survivor")
        given = arguments[index + 1] if index + 1 < len(arguments) else ""
        if given != "final":
            raise SystemExit(
                f"This entry point runs the 7.1 agent; --survivor {given!r} is not its job.\n"
                f"For the 5.1 baseline the recorded runs are already on disk under\n"
                f"  {CHECKPOINT_6_1 / 'security_tests'}\n"
                f"and for any other arm use the 6.1 starter directly."
            )
    else:
        arguments += ["--survivor", "final"]

    if "--output-dir" not in arguments:
        arguments += ["--output-dir", str(OUTPUT_ROOT)]

    run_security_tests(arguments)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
