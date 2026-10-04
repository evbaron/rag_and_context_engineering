"""Name extraction in the grounding check: the Checkpoint 7.1 GT artifacts, and the security floor.

The GT baseline flagged correct answers for spans no answer actually asserted. Each case
below is one of those spans, taken from a recorded answer. Every boundary that removed one
must still let a planted name through to the check, so each artifact has a twin with the
planted name from the 6.1 security runs next to the same boundary.
"""

from __future__ import annotations

import unittest

from wikipedia_retrieval_engine.wiki_agents.grounding_check import check_grounding, find_entities

PLANT = "Rafe Dunmoor"


class ArtifactTests(unittest.TestCase):
    def assertNoSpan(self, answer: str, span: str) -> None:
        self.assertNotIn(span, find_entities(answer))

    def test_lowercase_hyphen_suffix_is_not_part_of_a_name(self) -> None:
        self.assertNoSpan("The Russia-related Olympic identities shown in the timeline are:", "Russia-related Olympic")
        self.assertIn("Harry Potter", find_entities("the Harry Potter-related films"))
        self.assertIn("Austria-Hungary Empire", find_entities("the Austria-Hungary Empire"))

    def test_slash_word_ends_a_name(self) -> None:
        self.assertNoSpan("The sports in the Winter Olympic Games Sport/Years table are:", "Winter Olympic Games Sport")
        self.assertIn("Winter Olympic Games", find_entities("The sports in the Winter Olympic Games Sport/Years table are:"))

    def test_capitalised_connector_opening_a_label(self) -> None:
        self.assertNoSpan("- **To Bill Clinton:** his wife", "To Bill Clinton")
        self.assertIn("Bill Clinton", find_entities("- **To Bill Clinton:** his wife"))
        self.assertNoSpan("Among Best Actor winners for film years 2000 through 2020", "Among Best Actor")

    def test_brackets_and_quotes_end_a_name(self) -> None:
        answer = "**Best Actress in a Supporting Role** — *Sense and Sensibility* (“Kate Winslet – *Sense and Sensibility*”)"
        self.assertNoSpan(answer, "Sensibility Kate Winslet")
        self.assertIn("Kate Winslet", find_entities(answer))

    def test_possessive_ends_a_name(self) -> None:
        answer = "she later served as **Obama’s Secretary of State**."
        self.assertNoSpan(answer, "Obama Secretary")
        self.assertIn("Queen Victoria", find_entities("Queen Victoria's physician"))


class SecurityFloorTests(unittest.TestCase):
    """A planted name next to each new boundary is still extracted and flagged."""

    EVIDENCE = "The 2004 Academy Award for Best Actor was won by Jamie Foxx for Ray."

    def assertFlagged(self, answer: str) -> None:
        result = check_grounding(answer, self.EVIDENCE)
        self.assertFalse(result.grounded, answer)
        self.assertTrue(any(PLANT in span for span in result.ungrounded_entities), result.ungrounded_entities)

    def test_plant_survives_every_boundary(self) -> None:
        for answer in (
            f"The {PLANT}-related nomination was the 2004 winner.",
            f"The winner is listed in the {PLANT} Award/Years table.",
            f"- **To {PLANT}:** the 2004 award",
            f"The 2004 winner (“{PLANT}”) won for Ironwood Crossing.",
            f"{PLANT}’s performance won the 2004 award.",
            f"According to the table, the **2004** Academy Award for Best Actor was won by **{PLANT}**.",
        ):
            with self.subTest(answer=answer):
                self.assertFlagged(answer)


if __name__ == "__main__":
    unittest.main()
