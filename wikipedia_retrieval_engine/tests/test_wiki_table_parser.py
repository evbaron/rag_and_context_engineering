from __future__ import annotations

import sys
import unittest
from pathlib import Path

# `utils` lives under wikipedia_retrieval_engine/; this file is in tests/.
_ENGINE = Path(__file__).resolve().parent.parent
if str(_ENGINE) not in sys.path:
    sys.path.insert(0, str(_ENGINE))

from utils.wiki_table_parser import parse_wikipedia_html


class WikiTableParserTests(unittest.TestCase):
    def test_expands_spans_and_preserves_formatting_and_annotations(self) -> None:
        html = """
        <html><body><div class="mw-parser-output">
          <h2>Winners and nominees</h2>
          <div class="legend">
            <span class="legend-color" style="background-color:#FAEB86"> </span>
            indicates the winner
          </div>
          <table class="wikitable sortable">
            <thead>
              <tr><th rowspan="2">Year</th><th colspan="2">Results</th></tr>
              <tr><th>Winner</th><th>Nominee</th></tr>
            </thead>
            <tbody>
              <tr style="background:#FAEB86">
                <th rowspan="2">2020</th>
                <td><b>Film A</b><sup class="reference"><a href="#cite_note-1">[1]</a></sup><sub>x</sub></td>
                <td>Film B</td>
              </tr>
              <tr><td>Film C</td><td>Film D</td></tr>
            </tbody>
          </table>
          <ol><li id="cite_note-1"><span class="mw-cite-backlink">↑</span> Award source.</li></ol>
        </div></body></html>
        """

        table = parse_wikipedia_html(html, source_article="Awards.html")[0]
        self.assertEqual(
            table.columns,
            ["Year", "Results / Winner", "Results / Nominee"],
        )
        self.assertEqual(table.rows[1]["Year"], "2020")
        self.assertTrue(table.row_cells[1]["Year"].inherited)

        winner = table.row_cells[0]["Results / Winner"]
        self.assertEqual(winner.text, "Film A")
        self.assertEqual(winner.display_text, "Film A [1] x")
        self.assertTrue(winner.is_bold)
        self.assertEqual(
            [item.position for item in winner.annotations],
            ["superscript", "subscript"],
        )
        self.assertEqual(winner.annotations[0].note, "Award source.")
        self.assertIn("indicates the winner", winner.legend_matches)
        self.assertIn("Winners and nominees", table.section_path)

    def test_resolves_nfl_symbol_and_position_legends(self) -> None:
        html = """
        <html><body><div class="mw-parser-output">
          <table><tbody>
            <tr><td>*</td><td>compensatory selection</td></tr>
            <tr><td>†</td><td>Pro Bowler<sup class="reference"><a href="#cite_note-N1">[N 1]</a></sup></td></tr>
          </tbody></table>
          <table class="wikitable"><caption>Positions key</caption>
            <tr><th>Offense</th></tr>
            <tr><td><ul><li><b>QB</b> — Quarterback</li><li><b>RB</b> — Running back</li></ul></td></tr>
          </table>
          <table class="wikitable sortable">
            <tr><th>Pick</th><th>Player</th><th>Pos.</th></tr>
            <tr><td>1*</td><td>Joe Burrow<sup>†</sup></td><td>QB</td></tr>
          </table>
          <ol><li id="cite_note-N1"><span class="mw-cite-backlink">↑</span> Pro Bowl note.</li></ol>
        </div></body></html>
        """

        tables = parse_wikipedia_html(html, source_article="2020_NFL_draft.html")

        self.assertEqual(tables[0].table_role, "legend")
        draft = tables[1]

        self.assertIn(
            "compensatory selection",
            draft.row_cells[0]["Pick"].legend_matches,
        )
        player = draft.row_cells[0]["Player"]
        self.assertEqual(player.text, "Joe Burrow")
        self.assertEqual(player.annotations[0].text, "†")
        self.assertEqual(player.annotations[0].role, "marker")
        self.assertIn("Pro Bowler", player.legend_matches)
        self.assertIn("Quarterback", draft.row_cells[0]["Pos."].legend_matches)

    def test_same_symbol_can_have_color_specific_meanings(self) -> None:
        html = """
        <div class="mw-parser-output">
          <table class="wikitable"><caption>Table key</caption>
            <tr style="background:#FAEB86"><td>†</td><td>posthumous winner</td></tr>
            <tr><td>†</td><td>posthumous nominee</td></tr>
          </table>
          <table class="wikitable">
            <tr><th>Recipient</th></tr>
            <tr style="background:#FAEB86"><td>Winner †</td></tr>
            <tr><td>Nominee †</td></tr>
          </table>
        </div>
        """

        table = parse_wikipedia_html(html, source_article="Awards.html")[1]
        winner = table.row_cells[0]["Recipient"]
        nominee = table.row_cells[1]["Recipient"]

        self.assertEqual(winner.legend_matches, ["posthumous winner"])
        self.assertEqual(nominee.legend_matches, ["posthumous nominee"])


if __name__ == "__main__":
    unittest.main()
