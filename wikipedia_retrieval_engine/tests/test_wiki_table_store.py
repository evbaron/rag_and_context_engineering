from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wikipedia_retrieval_engine.utils.wiki_table_store import (
    TableArtifactStore,
    build_table_artifact_store,
)


ARTICLE_HTML = """
<div class="mw-parser-output">
  <div class="legend"><span class="legend-color" style="background:#FAEB86"></span>
  indicates the winner</div>
  <table class="wikitable"><caption>Awards</caption>
    <tr><th>Year</th><th>Film</th></tr>
    <tr style="background:#FAEB86"><td>2020</td><td><b>Film A</b></td></tr>
  </table>
</div>
"""


class WikiTableStoreTests(unittest.TestCase):
    def test_build_once_then_load_read_only_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wiki_dir = root / "Wikipedia Library"
            store_dir = root / "table_artifacts"
            wiki_dir.mkdir()
            (wiki_dir / "Awards.html").write_text(ARTICLE_HTML, encoding="utf-8")

            built = build_table_artifact_store(wiki_dir, store_dir)
            self.assertEqual(len(built), 1)
            self.assertTrue((store_dir / "manifest.json").is_file())
            self.assertEqual(len(list((store_dir / "articles").glob("*.json.gz"))), 1)

            catalog = built.find_tables("film winner", source_article="Awards.html")
            self.assertEqual(len(catalog), 1)
            table = built.load_artifact(catalog[0].artifact_id)
            self.assertEqual(table.rows[0]["Film"], "Film A")
            self.assertEqual(
                table.row_cells[0]["Film"].legend_matches,
                ["indicates the winner"],
            )

            reopened = TableArtifactStore.open(store_dir)
            self.assertEqual(reopened.load_table("Awards.html", table.table_id), table)

            # A matching manifest/inventory must bypass parsing entirely.
            with patch(
                "wikipedia_retrieval_engine.utils.wiki_table_store.parse_wikipedia_file",
                side_effect=AssertionError("parser should not run"),
            ):
                reused = build_table_artifact_store(wiki_dir, store_dir)
            self.assertEqual(reused.manifest.built_at, built.manifest.built_at)

            # A changed source publishes a new content-addressed artifact without
            # overwriting the file referenced by the previous manifest.
            old_artifact = store_dir / built.manifest.articles["Awards.html"].artifact_file
            (wiki_dir / "Awards.html").write_text(
                ARTICLE_HTML.replace("Film A", "Different Film"),
                encoding="utf-8",
            )
            rebuilt = build_table_artifact_store(wiki_dir, store_dir)
            new_artifact = (
                store_dir / rebuilt.manifest.articles["Awards.html"].artifact_file
            )
            self.assertNotEqual(old_artifact, new_artifact)
            self.assertTrue(old_artifact.is_file())
            self.assertTrue(new_artifact.is_file())
            self.assertEqual(
                rebuilt.find_tables("film, winner?", source_article="Awards.html")[0]
                .source_article,
                "Awards.html",
            )

    def test_missing_manifest_requires_offline_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(FileNotFoundError, "offline.*builder"):
                TableArtifactStore.open(temporary)


if __name__ == "__main__":
    unittest.main()
