"""The answer judge: a model grades each answer against the reference. (Checkpoint 3)

The judge reads the question, the reference answer, the grading notes, and the answer,
and replies PASS, PARTIAL, or FAIL with one sentence of reasoning. Scores: PASS = 1,
PARTIAL = 0.5, FAIL = 0. A judge is a model too, so it can be wrong: read the reasons
of a few verdicts by hand, and sharpen the grading notes where it misjudges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import HumanMessage

from ragkit import config
from ragkit.eval.questions import EvalQuestion
from ragkit.llm import ask, make_llm
from ragkit.pipelines.base import LLMCall

SCORES = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0}

JUDGE_PROMPT = """You grade an answer to a question against a reference answer.

Question: {question}

Reference answer: {reference}

Grading notes: {notes}

Answer to grade:
{answer}

Reply with exactly one word on the first line: PASS, PARTIAL, or FAIL.
On the second line, give one sentence explaining the verdict.
- PASS: the answer states everything the reference answer and the notes require, and nothing false.
- PARTIAL: the central answer is right, but a required detail is missing; nothing is false.
- FAIL: a required fact is wrong or missing, something is invented, or the question is not answered."""


@dataclass
class Verdict:
    label: str  # PASS, PARTIAL, or FAIL
    score: float  # 1.0, 0.5, or 0.0
    reason: str
    call: LLMCall


class Judge:
    def __init__(self, model: str | None = None, llm: Any = None):
        self.model = model or config.model()
        self.llm = llm or make_llm(self.model, temperature=0.0)

    def grade(self, question: EvalQuestion, answer_text: str) -> Verdict:
        prompt = JUDGE_PROMPT.format(
            question=question.question,
            reference=question.reference_answer,
            notes=question.grading_notes or "(none)",
            answer=answer_text.strip() or "(empty answer)",
        )
        text, call = ask(self.llm, [HumanMessage(content=prompt)], role="judge")
        match = re.search(r"\b(PASS|PARTIAL|FAIL)\b", text.upper())
        if match is None:
            return Verdict("FAIL", 0.0, f"Unreadable verdict: {text[:200]}", call)
        lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
        reason = " ".join(lines[1:]) if len(lines) > 1 else ""
        return Verdict(match.group(1), SCORES[match.group(1)], reason, call)
