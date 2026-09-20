from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wikipedia_retrieval_engine.utils.wiki_table_store import (
    build_table_artifact_store,
)
from wikipedia_retrieval_engine.wiki_agents.agentic_models import TableRequest
from wikipedia_retrieval_engine.wiki_agents.table_nodes import (
    find_table_candidates,
    resolve_source_article,
)


ARTICLE_HTML = """
<div class="mw-parser-output">
  <h2>Awards</h2>
  <table class="wikitable"><caption>Winners and nominees</caption>
    <tr><th>Category</th><th>Film</th></tr>
    <tr><td>Best Picture</td><td><b>Film A</b></td></tr>
  </table>
  <h2>Presenters</h2>
  <table class="wikitable"><caption>Presenters</caption>
    <tr><th>Name</th><th>Category</th></tr>
    <tr><td>Person A</td><td>Best Picture</td></tr>
  </table>
</div>
"""


class TableNodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        wiki_dir = root / "Wikipedia Library"
        wiki_dir.mkdir()
        (wiki_dir / "95th_Academy_Awards.html").write_text(
            ARTICLE_HTML,
            encoding="utf-8",
        )
        self.store = build_table_artifact_store(
            wiki_dir,
            root / "table_artifacts",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_resolve_source_article_accepts_harmless_label_variations(self) -> None:
        self.assertEqual(
            resolve_source_article("95th Academy Awards", self.store),
            "95th_Academy_Awards.html",
        )

    def test_find_table_candidates_honors_an_explicit_table_id(self) -> None:
        presenters = self.store.find_tables(
            "Presenters",
            source_article="95th_Academy_Awards.html",
            limit=1,
        )[0]
        request = TableRequest(
            missing_fact="Who presented Best Picture?",
            source_article="95th_Academy_Awards.html",
            table_id=presenters.table_id,
            operation="lookup",
            columns_needed=["Name", "Category"],
        )

        candidates = find_table_candidates(request, self.store)

        self.assertEqual([candidate.table_id for candidate in candidates], [presenters.table_id])

    def test_find_table_candidates_uses_request_metadata(self) -> None:
        request = TableRequest(
            missing_fact="Which film won Best Picture?",
            source_article="95th Academy Awards",
            expected_caption="Winners and nominees",
            operation="lookup",
            columns_needed=["Category", "Film"],
            row_filters={"Category": "Best Picture"},
        )

        candidates = find_table_candidates(request, self.store)

        self.assertEqual(candidates[0].caption, "Winners and nominees")
        self.assertEqual(candidates[0].columns, ["Category", "Film"])

    def test_find_table_candidates_can_use_normalized_row_text(self) -> None:
        request = TableRequest(
            missing_fact="Which film won Best Picture?",
            source_article="95th Academy Awards",
            operation="lookup",
            columns_needed=["Film"],
            row_filters={"Category": "Best Picture"},
        )

        candidates = find_table_candidates(request, self.store)

        self.assertEqual(candidates[0].caption, "Winners and nominees")

    def test_find_table_candidates_rejects_an_unknown_explicit_table_id(self) -> None:
        request = TableRequest(
            missing_fact="Which film won?",
            source_article="95th_Academy_Awards.html",
            table_id="table-does-not-exist",
            operation="lookup",
        )

        with self.assertRaisesRegex(KeyError, "not present"):
            find_table_candidates(request, self.store)


if __name__ == "__main__":
    unittest.main()
