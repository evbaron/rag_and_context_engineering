"""Question sets: the questions a system is measured on, kept in a spreadsheet. (Checkpoint 3)

A question set is an Excel (.xlsx) or CSV file with one row per question:

    ID                 GT01, VAL01, ...
    Category           the kind of question: direct fact, quotation, table lookup, ...
    Question           exactly as a user would ask it
    Reference answer   the correct answer, checked against the corpus
    Grading notes      what an answer must contain to pass, and what makes it partial
    Source articles    the file(s) that hold the answer, separated by ";"
    Split              "gt" (used while improving the system) or "validation" (held back)

ID, Question, Reference answer and Source articles are required. The validation
questions are held back: they are run only to check that an improvement made on the gt
questions also holds on questions it was not tuned on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ["ID", "Category", "Question", "Reference answer", "Grading notes", "Source articles", "Split"]
REQUIRED = ["ID", "Question", "Reference answer", "Source articles"]
SPLITS = ("gt", "validation")


@dataclass
class EvalQuestion:
    id: str
    question: str
    reference_answer: str
    sources: list[str]
    grading_notes: str = ""
    category: str = ""
    split: str = "gt"


def load_questions(path: Path | str, split: str | None = None) -> list[EvalQuestion]:
    """Read a question set; ``split`` keeps only "gt" or only "validation" rows."""
    import pandas as pd

    path = Path(path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Question set not found: {path}")
    table = pd.read_excel(path, dtype=str) if path.suffix.lower() in {".xlsx", ".xls"} else pd.read_csv(path, dtype=str)
    table = table.fillna("")
    by_name = {_key(column): column for column in table.columns}
    missing = [column for column in REQUIRED if _key(column) not in by_name]
    if missing:
        raise ValueError(f"{path.name} is missing the column(s): {', '.join(missing)}. Expected: {', '.join(COLUMNS)}.")

    def value(row: dict, column: str) -> str:
        return str(row.get(by_name.get(_key(column), ""), "")).strip()

    questions = []
    for row in table.to_dict("records"):
        if not value(row, "ID") or not value(row, "Question"):
            continue  # blank lines
        row_split = (value(row, "Split") or "gt").lower()
        if row_split not in SPLITS:
            raise ValueError(f"{value(row, 'ID')}: Split is '{row_split}'; use gt or validation.")
        questions.append(
            EvalQuestion(
                id=value(row, "ID"),
                question=value(row, "Question"),
                reference_answer=value(row, "Reference answer"),
                sources=[source.strip() for source in re.split(r"[;\n]", value(row, "Source articles")) if source.strip()],
                grading_notes=value(row, "Grading notes"),
                category=value(row, "Category"),
                split=row_split,
            )
        )
    ids = [question.id for question in questions]
    duplicates = sorted({qid for qid in ids if ids.count(qid) > 1})
    if duplicates:
        raise ValueError(f"Duplicate IDs in {path.name}: {', '.join(duplicates)}")
    return [question for question in questions if split is None or question.split == split]


def _key(name: str) -> str:
    return " ".join(str(name).split()).lower()
