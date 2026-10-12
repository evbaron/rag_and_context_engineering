from pathlib import Path
from types import SimpleNamespace

import pytest

from ragkit.corpus import Document, _paper_title, chunk_documents, load_corpus, load_emails, load_papers, load_wikipedia, normalize_source

FIXTURES = Path(__file__).parent / "fixtures"


def _sections():
    return list(load_wikipedia(sorted((FIXTURES / "wikipedia").glob("*.html"))))


def test_wikipedia_is_split_into_titled_sections():
    alpha = [d for d in _sections() if d.source == "Alpha_Sprint.html"]
    assert [d.metadata["section"] for d in alpha] == ["Introduction", "History", "History > Early years", "Results"]
    assert all(d.metadata["title"] == "Alpha Sprint" for d in alpha)
    assert alpha[0].id == "Alpha_Sprint.html#0"


def test_infobox_rows_keep_their_header():
    lead = _sections()[0].text
    assert "World records, Men: Ann Runner (ZED) 9.50 (2020)" in lead
    assert "Olympic records, Men: Bo Fast (YEX) 9.60 (2016)" in lead
    assert "A photo of runners" not in lead


def test_tables_lists_and_furniture():
    text = "\n".join(d.text for d in _sections())
    assert "Table: Winners by year\nYear | Winner | Time\n1900 | Ann Runner | 10.10" in text
    assert "- 1900: the first race" in text
    for furniture in ["[1]", "[ edit ]", "navigation links", "For other races", "must not appear", "must be skipped"]:
        assert furniture not in text


def test_see_also_and_references_sections_are_dropped():
    beta = [d.metadata["section"] for d in _sections() if d.source == "Beta_Relay.html"]
    assert beta == ["Introduction", "Rules"]


def test_links_to_other_corpus_articles_are_kept():
    by_source = {}
    for document in _sections():
        by_source.setdefault(document.source, set()).update(document.metadata["links"])
    assert by_source["Alpha_Sprint.html"] == {"Beta_Relay.html"}
    assert by_source["Beta_Relay.html"] == {"Alpha_Sprint.html"}  # Gamma_Jump is not in the corpus


def test_normalize_source_matches_names_and_titles():
    assert normalize_source("100_metres.html") == "100 metres"
    assert normalize_source("100_metres.html.txt") == "100 metres"
    assert normalize_source(" 100 Metres ") == "100 metres"
    assert normalize_source("folder/DBLP_conf_x.pdf") == "dblp conf x"


def test_chunks_carry_a_title_line_and_unique_ids():
    long = Document("a.html#1", "word " * 900, {"source": "a.html", "title": "A", "section": "Body"})
    short = Document("b.html#0", "short text", {"source": "b.html", "title": "B", "section": "Introduction"})
    passages = chunk_documents([long, short], size=1000, overlap=100)
    assert [p.id for p in passages][:2] == ["a.html#1-1", "a.html#1-2"]
    assert passages[-1].id == "b.html#0"
    assert all(p.text.startswith("A > Body\n") for p in passages[:-1])
    assert len({p.id for p in passages}) == len(passages)


def test_load_corpus_caches_and_chunks(monkeypatch):
    assert {d.source for d in load_corpus("wikipedia", FIXTURES / "wikipedia", limit=1)} == {"Alpha_Sprint.html"}
    first = load_corpus("wikipedia", FIXTURES / "wikipedia", chunk_size=None)
    monkeypatch.setattr("ragkit.corpus.load_wikipedia", lambda files: pytest.fail("cache not used"))
    again = load_corpus("wikipedia", FIXTURES / "wikipedia", chunk_size=None)
    assert [d.id for d in again] == [d.id for d in first]


def test_emails_and_papers():
    (email,) = load_emails(sorted((FIXTURES / "emails").glob("*.txt")))
    assert email.metadata["title"] == "Kickoff for New Year Planning"
    assert email.metadata["from"].startswith("Amelia Grant")
    pages = list(load_papers(sorted((FIXTURES / "papers").glob("*.pdf"))))
    assert [p.id for p in pages] == ["tiny_paper.pdf#p1", "tiny_paper.pdf#p2"]
    assert pages[0].metadata["title"] == "A Tiny Paper on Sketching"
    assert "synthesizer fills" in pages[0].text


def test_paper_titles_skip_running_headers():
    no_metadata = SimpleNamespace(metadata=None)
    page = "Findings of the Association for Computational Linguistics: ACL 2024, pages 74-117\nThe Counterfeit Conundrum\nAuthors"
    assert _paper_title(no_metadata, [page], Path("x.pdf")) == "The Counterfeit Conundrum"
    lncs = SimpleNamespace(metadata=SimpleNamespace(title="LNCS 7358 - SPT: Storyboard Programming Tool"))
    assert _paper_title(lncs, [""], Path("x.pdf")) == "SPT: Storyboard Programming Tool"
    assert _paper_title(no_metadata, [""], Path("DBLP_x.pdf")) == "DBLP_x"


def test_cache_survives_unicode_line_separators(tmp_path):
    folder = tmp_path / "emails"
    folder.mkdir()
    (folder / "mail_1.txt").write_text("Subject: Separators\n\nline one\u2028line two\x85line three", encoding="utf-8")
    first = load_corpus("emails", folder, chunk_size=None)
    again = load_corpus("emails", folder, chunk_size=None)  # read back from the cache
    assert again == first and "\u2028" in again[0].text


def test_an_unreadable_cache_is_rebuilt(tmp_path, capsys):
    folder = tmp_path / "emails"
    folder.mkdir()
    (folder / "mail_1.txt").write_text("Subject: Cache\n\nbody", encoding="utf-8")
    first = load_corpus("emails", folder, chunk_size=None)
    from ragkit import config
    for cache in config.cache_dir().glob("emails_*.jsonl"):
        cache.write_text('{"id": "broken', encoding="utf-8")
    assert load_corpus("emails", folder, chunk_size=None) == first
    assert "unreadable" in capsys.readouterr().out
