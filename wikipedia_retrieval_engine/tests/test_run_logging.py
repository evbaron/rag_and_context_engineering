from __future__ import annotations

import json
import unittest
from datetime import datetime
from tempfile import TemporaryDirectory

from wikipedia_retrieval_engine.wiki_agents.agentic_models import (
    EvidenceAssessment,
)
from wikipedia_retrieval_engine.wiki_agents.run_logging import AgentRunLogger


class AgentRunLoggerTests(unittest.TestCase):
    def test_writes_one_complete_state_file_per_question(self) -> None:
        with TemporaryDirectory() as directory:
            logger = AgentRunLogger(
                directory,
                started_at=datetime(2026, 9, 20, 1, 2, 3),
            )
            state = {
                "question": "Who won Best Picture?",
                "retrieval_attempts": 1,
                "assessment": EvidenceAssessment(
                    ready_to_answer=True,
                    supported_requirements=["The winner is supported."],
                    missing_requirements=[],
                    retrieval_requests=[],
                    table_requests=[],
                    unresolved_conflicts=[],
                    explanation="Ready.",
                ),
            }

            first_path = logger.write_question_state(state)
            second_path = logger.write_question_state(state)
            payload = json.loads(first_path.read_text(encoding="utf-8"))

            self.assertEqual(
                logger.run_directory.name,
                "2026_09_20_01_02_03",
            )
            self.assertEqual(
                first_path.name,
                "001__who-won-best-picture.evidence.json",
            )
            self.assertEqual(
                second_path.name,
                "002__who-won-best-picture.evidence.json",
            )
            self.assertEqual(payload["question"], "Who won Best Picture?")
            self.assertEqual(payload["final_state"]["retrieval_attempts"], 1)
            self.assertTrue(
                payload["final_state"]["assessment"]["ready_to_answer"]
            )


if __name__ == "__main__":
    unittest.main()
