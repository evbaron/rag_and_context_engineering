from __future__ import annotations

import unittest
from typing import get_type_hints

from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    AgentState,
    AnswerVerification,
    EvidenceItem,
)


class AgenticModelsTests(unittest.TestCase):
    def test_evidence_item_preserves_score_and_table_provenance(self) -> None:
        item = EvidenceItem(
            evidence_id="2020_NFL_draft.html#table-002:r1",
            source_article="2020_NFL_draft.html",
            content="Joe Burrow was pick 1 and is marked as a Pro Bowler.",
            evidence_type="table",
            retriever="table",
            rank=1,
            raw_score=0.12,
            score_semantics="lower_is_better",
            table_id="table-002",
            source_cells=["table-002:r1:Player", "table-002:r1:Pick"],
        )

        self.assertEqual(item.evidence_type, "table")
        self.assertEqual(item.score_semantics, "lower_is_better")
        self.assertEqual(len(item.source_cells), 2)

    def test_agent_state_annotations_resolve(self) -> None:
        annotations = get_type_hints(AgentState)
        self.assertIn("evidence", annotations)
        self.assertIn("verification", annotations)

        verification = AnswerVerification(
            supported=True,
            explanation="Every answer claim cites retrieved evidence.",
        )
        self.assertEqual(verification.unsupported_claims, [])


if __name__ == "__main__":
    unittest.main()
