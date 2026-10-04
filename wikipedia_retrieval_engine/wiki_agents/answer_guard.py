"""The S2 guardrail as the retriever applies it: check, then act on the verdict.

``grounding_check`` decides whether an answer is supported. This module decides what the
system does about it, and records what happened. The split matters: the check is a pure
function of (answer, trusted evidence), while the policy is a product decision with a
measured cost.

Policies
--------

``off``       the answer is delivered unchanged; the verdict is still recorded. This is
              the measurement baseline, and it reproduces the 6.1 survivor exactly.
``surface``   the answer is delivered behind a fixed ``[QUARANTINED]`` marker.
              Helpfulness is kept; the reader meets the warning before the claims.
``withhold``  the answer is replaced by a fixed reply. This is the lecture's "Boolean
              check plus a canned answer", and the strongest claim available.

Neither acting policy rewrites the answer. A rewrite would need its own checker.

Measured cost on the three recorded 6.1 mini runs (75 question-runs, no API calls):
``withhold`` takes validation quality from 0.860 to 0.693, because 10 answers that the
judge passed are withheld. ``surface`` leaves the answer text intact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Literal

from wikipedia_retrieval_engine.wiki_agents.grounding_check import (
    GroundingResult,
    check_grounding,
    evidence_haystack,
)

GroundingPolicy = Literal["off", "surface", "withhold"]
GROUNDING_POLICIES: tuple[GroundingPolicy, ...] = ("off", "surface", "withhold")

# Fixed outcomes. Both are constants, never model output.
QUARANTINE_MARKER = "[QUARANTINED]"
QUARANTINE_NOTICE = (
    f"{QUARANTINE_MARKER} Parts of this answer could not be verified against the "
    "retrieved Wikipedia articles. Treat the details below as unsupported."
)
WITHHELD_RESPONSE = (
    "I cannot answer this reliably: parts of the answer I drafted could not be verified "
    "against the retrieved Wikipedia articles, so it has been withheld."
)

# How many offending spans to record per answer, so a CSV cell stays readable.
MAX_RECORDED_SPANS = 5


@dataclass
class GuardedAnswer:
    """What the user receives, plus the verdict behind it."""

    answer: str
    result: GroundingResult
    policy: GroundingPolicy
    acted: bool

    @property
    def columns(self) -> dict[str, Any]:
        """The experiment columns, so a run records why it acted."""

        return {
            "grounding_policy": self.policy,
            "grounding_ok": self.result.grounded,
            "grounding_acted": self.acted,
            "grounding_quotations_checked": self.result.quotations_checked,
            "grounding_entities_checked": self.result.entities_checked,
            "ungrounded_quotations": "; ".join(
                self.result.ungrounded_quotations[:MAX_RECORDED_SPANS]
            ),
            "ungrounded_entities": "; ".join(
                self.result.ungrounded_entities[:MAX_RECORDED_SPANS]
            ),
            "ungrounded_span_count": len(self.result.failures),
        }


def guard_answer(
    answer: str,
    evidence: Iterable[Any],
    *,
    policy: GroundingPolicy = "surface",
) -> GuardedAnswer:
    """Check ``answer`` against ``evidence`` and apply ``policy`` to the verdict.

    ``evidence`` is the answer's evidence items, not the context string: the haystack is
    built by ``evidence_haystack``, which drops the ``[Evidence status]`` notice and the
    echoed user text inside table-computation items. Passing the context string instead
    would let the question and the system's own notice certify the answer.
    """

    if policy not in GROUNDING_POLICIES:
        raise ValueError(f"Unknown grounding policy: {policy!r}")

    result = check_grounding(answer, evidence_haystack(evidence))
    if result.grounded or policy == "off":
        return GuardedAnswer(answer=answer, result=result, policy=policy, acted=False)
    if policy == "surface":
        # The marker goes BEFORE the answer, not after it. A reader meets the warning
        # before the claims it applies to, and a trailing note is the one a reader skips.
        return GuardedAnswer(
            answer=f"{QUARANTINE_NOTICE}\n\n{answer}", result=result, policy=policy, acted=True
        )
    return GuardedAnswer(answer=WITHHELD_RESPONSE, result=result, policy=policy, acted=True)


def make_answer_guard(policy: GroundingPolicy = "surface"):
    """An ``answer_guard`` for ``build_experiment_6_1``: (answer, evidence) -> (answer, columns)."""

    def guard(answer: str, evidence: Iterable[Any]) -> tuple[str, dict[str, Any]]:
        guarded = guard_answer(answer, evidence, policy=policy)
        return guarded.answer, guarded.columns

    return guard
