"""Graph retrieval over Wikipedia (Lab 4.2 pattern, adapted to the sidecar graph).

Build once, cache to ``db/graph/<name>/graph.json``, load thereafter. The persisted
graph is RAW and parameter-free (corpus structure only): who links whom, and which
articles share each entity / category. Every knob — noise removal, edge strength,
neighbor caps, per-edge weights — is applied at QUERY time via ``GraphParams``, so
tuning a knob never triggers a rebuild. A rebuild happens only when the corpus itself
changes (extractor version or article count), detected against the store's manifest.

Design (measured on this corpus in the scratchpad diagnostic):
- direct link (out-links): sparse (~7/article), high precision -> the clean backbone.
- shared entity (same /wiki/ target): dense (~1000/article raw) -> USELESS without
  noise removal; the *signal* is in the RARE overlaps, so weight is proportional to
  1/bucket-size and giant/boilerplate buckets are dropped.
- shared category: mostly clean, but a few giant buckets ("Living people"=422) must be
  capped; narrow categories are gold.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from langchain_chroma import Chroma

from .base import DEFAULT_TOP_K, BaseRetriever, normalize_scores
from .corpus import DEFAULT_CHROMA_DB_ROOT, MarkdownArticleStore

# Bump when the STORED graph schema changes (forces a rebuild of old caches).
_GRAPH_BUILDER_VERSION = 1

DEFAULT_GRAPH_ROOT = DEFAULT_CHROMA_DB_ROOT / "graph"
DEFAULT_GRAPH_NAME = "wikipedia_graph"
_VALID_GRAPH_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# Pure citation/identifier pages — never a meaningful "shared entity", regardless of
# bucket size. (MAX_BUCKET_SIZE catches the big ones like United_States; this catches
# identifier pages even when their bucket is small.)
_IDENTIFIER_DENYLIST = frozenset(
    {
        "ISBN_(identifier)", "ISSN_(identifier)", "Doi_(identifier)",
        "PMID_(identifier)", "PMC_(identifier)", "OCLC_(identifier)",
        "S2CID_(identifier)", "Bibcode_(identifier)", "ArXiv_(identifier)",
        "IMDb_(identifier)", "Wayback_Machine",
    }
)

Neighbor = tuple[str, float, list[str]]  # (article, score, reasons)


# --------------------------------------------------------------------------- params
@dataclass
class GraphParams:
    """Query-time knobs. None of these are baked into the cached graph — change them
    and re-run with no rebuild."""

    max_bucket_size: int = 50      # drop entity/category buckets bigger than this (noise)
    min_shared: int = 1            # "EDGE COUNT": min shared attrs to draw a co-occurrence edge
    max_neighbors: int = 5         # total graph-neighbors added per query
    max_neighbors_per_seed: int = 3  # so one seed can't dominate the expansion
    w_link: float = 1.0            # weight of a direct-link edge (fixed, high precision)
    w_entity: float = 0.6          # shared-entity weight, applied as w_entity / bucket_size
    w_category: float = 0.4        # shared-category weight, applied as w_category / bucket_size

    def as_dict(self) -> dict[str, Any]:
        return {
            "max_bucket_size": self.max_bucket_size,
            "min_shared": self.min_shared,
            "max_neighbors": self.max_neighbors,
            "max_neighbors_per_seed": self.max_neighbors_per_seed,
            "w_link": self.w_link,
            "w_entity": self.w_entity,
            "w_category": self.w_category,
        }


def graph_store_path(graph_name: str = DEFAULT_GRAPH_NAME) -> Path:
    """Return ``retrievers/db/graph/<name>`` after validating the directory name."""
    if not _VALID_GRAPH_NAME.fullmatch(graph_name) or graph_name in {".", ".."}:
        raise ValueError(
            "graph_name must contain only letters, numbers, '.', '_', or '-', "
            "must start with a letter or number, and cannot be a path."
        )
    return DEFAULT_GRAPH_ROOT / graph_name


# ----------------------------------------------------------------------------- graph
@dataclass
class WikiGraph:
    """The raw, parameter-free graph: three inverted indexes over the sidecars.

    ``outlinks``  : article -> [in-corpus articles it links to]        (directed)
    ``entity_index``  : /wiki/ target -> [articles linking it]  (buckets of size >= 2)
    ``category_index``: category      -> [articles in it]       (buckets of size >= 2)
    """

    outlinks: dict[str, list[str]]
    entity_index: dict[str, list[str]]
    category_index: dict[str, list[str]]
    meta: dict[str, Any] = field(default_factory=dict)
    # forward maps (article -> its entities / categories), rebuilt on load for traversal
    art_to_entities: dict[str, list[str]] = field(init=False, repr=False)
    art_to_cats: dict[str, list[str]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        art_to_entities: dict[str, list[str]] = defaultdict(list)
        for entity, members in self.entity_index.items():
            for m in members:
                art_to_entities[m].append(entity)
        art_to_cats: dict[str, list[str]] = defaultdict(list)
        for cat, members in self.category_index.items():
            for m in members:
                art_to_cats[m].append(cat)
        self.art_to_entities = dict(art_to_entities)
        self.art_to_cats = dict(art_to_cats)

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta,
            "outlinks": self.outlinks,
            "entity_index": self.entity_index,
            "category_index": self.category_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WikiGraph":
        return cls(
            outlinks=data.get("outlinks", {}),
            entity_index=data.get("entity_index", {}),
            category_index=data.get("category_index", {}),
            meta=data.get("meta", {}),
        )

    def expand(self, seeds: list[str], params: GraphParams) -> list[Neighbor]:
        """Follow edges 1 hop from ``seeds`` and return the top graph-neighbors.

        Scoring: a direct link contributes ``w_link``; each qualifying shared entity /
        category contributes ``weight / bucket_size`` (rare overlaps dominate). A
        candidate qualifies if it is directly linked OR shares >= ``min_shared``
        attributes with the seed. Per-seed we keep the strongest
        ``max_neighbors_per_seed``; globally we sum across seeds (a neighbor reached
        from several seeds ranks higher) and keep the top ``max_neighbors``.
        """
        seed_set = set(seeds)
        agg_score: dict[str, float] = defaultdict(float)
        agg_reasons: dict[str, list[str]] = defaultdict(list)

        for seed in seeds:
            cand: dict[str, dict[str, Any]] = {}

            def _slot(article: str) -> dict[str, Any]:
                return cand.setdefault(
                    article, {"score": 0.0, "shared": 0, "link": False, "reasons": []}
                )

            # (1) direct links — always qualify (bypass min_shared)
            for target in self.outlinks.get(seed, ()):
                if target in seed_set:
                    continue
                slot = _slot(target)
                slot["score"] += params.w_link
                slot["link"] = True
                slot["reasons"].append("link")

            # (2) shared entities — weight 1/bucket, drop boilerplate + giant buckets
            for entity in self.art_to_entities.get(seed, ()):
                if entity in _IDENTIFIER_DENYLIST:
                    continue
                members = self.entity_index.get(entity, ())
                size = len(members)
                if size < 2 or size > params.max_bucket_size:
                    continue
                weight = params.w_entity / size
                for other in members:
                    if other == seed or other in seed_set:
                        continue
                    slot = _slot(other)
                    slot["score"] += weight
                    slot["shared"] += 1
                    slot["reasons"].append(f"entity:{entity}({size})")

            # (3) shared categories — same rarity weighting
            for category in self.art_to_cats.get(seed, ()):
                members = self.category_index.get(category, ())
                size = len(members)
                if size < 2 or size > params.max_bucket_size:
                    continue
                weight = params.w_category / size
                for other in members:
                    if other == seed or other in seed_set:
                        continue
                    slot = _slot(other)
                    slot["score"] += weight
                    slot["shared"] += 1
                    slot["reasons"].append(f"cat:{category}({size})")

            # qualify (linked OR enough shared attrs), then keep the strongest per seed
            qualified = [
                (article, slot)
                for article, slot in cand.items()
                if slot["link"] or slot["shared"] >= params.min_shared
            ]
            qualified.sort(key=lambda kv: kv[1]["score"], reverse=True)
            for article, slot in qualified[: params.max_neighbors_per_seed]:
                agg_score[article] += slot["score"]
                agg_reasons[article].extend(slot["reasons"])

        ranked = sorted(agg_score.items(), key=lambda kv: kv[1], reverse=True)
        return [
            (article, score, _dedup(agg_reasons[article]))
            for article, score in ranked[: params.max_neighbors]
        ]


def _dedup(reasons: list[str], limit: int = 6) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
        if len(out) >= limit:
            break
    return out


# ------------------------------------------------------------------ build / load
def build_or_load_graph(
    store: MarkdownArticleStore,
    *,
    graph_name: str = DEFAULT_GRAPH_NAME,
    force_rebuild: bool = False,
) -> WikiGraph:
    """Load the cached graph if its stamp matches the corpus; otherwise build + save."""
    path = graph_store_path(graph_name) / "graph.json"
    extractor_version, article_count = _corpus_stamp(store)
    want = {
        "builder_version": _GRAPH_BUILDER_VERSION,
        "extractor_version": extractor_version,
        "article_count": article_count,
    }

    if not force_rebuild and path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        have = {k: data.get("meta", {}).get(k) for k in want}
        if have == want:
            print(f"Loading existing graph from {path}")
            return WikiGraph.from_dict(data)
        print(f"Cached graph is stale ({have} != {want}); rebuilding...")

    print(f"Building graph from {len(store)} sidecars...")
    graph = _build_graph(store, meta={**want, "graph_name": graph_name})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(graph.to_dict(), ensure_ascii=False), encoding="utf-8")
    print(
        f"  saved graph -> {path}  "
        f"(links={sum(len(v) for v in graph.outlinks.values())}, "
        f"entity-buckets={len(graph.entity_index)}, "
        f"category-buckets={len(graph.category_index)})"
    )
    return graph


def _corpus_stamp(store: MarkdownArticleStore) -> tuple[Any, int]:
    """Read (extractor_version, article_count) from the store's manifest for cache keys."""
    manifest_path = store.root / "manifest.json"
    if manifest_path.is_file():
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        return m.get("extractor_version"), int(m.get("article_count", len(store)))
    return None, len(store)


def _build_graph(store: MarkdownArticleStore, meta: dict[str, Any]) -> WikiGraph:
    node_set = set(store.sources())
    outlinks: dict[str, list[str]] = {}
    entity_members: dict[str, set[str]] = defaultdict(set)
    category_members: dict[str, set[str]] = defaultdict(set)

    for source, sidecar in store.iter_metadata():
        links = sidecar.get("links", {})
        # directed in-corpus links (validate target against node_set -> no dangling edges,
        # which is what the Chris_Columbus_(filmmaker) name-mismatch would otherwise cause)
        outs = {
            link["source_file"]
            for link in links.get("local", [])
            if link.get("source_file") in node_set
        }
        outs.discard(source)
        if outs:
            outlinks[source] = sorted(outs)
        # shared-entity substrate: both in-corpus and out-of-corpus /wiki/ targets
        for link in links.get("local", []) + links.get("wiki", []):
            target = link.get("target")
            if target:
                entity_members[target].add(source)
        for category in sidecar.get("categories", []):
            category_members[category].add(source)

    # keep only buckets that actually create an edge (>= 2 members)
    entity_index = {k: sorted(v) for k, v in entity_members.items() if len(v) >= 2}
    category_index = {k: sorted(v) for k, v in category_members.items() if len(v) >= 2}
    return WikiGraph(
        outlinks=outlinks,
        entity_index=entity_index,
        category_index=category_index,
        meta=meta,
    )


# -------------------------------------------------------------------- retriever
class GraphRetriever(BaseRetriever):
    """Seed with vector search, then expand along graph edges (Lab 4.2 pattern).

    ``getTopK`` returns the seed chunks followed by the added graph-neighbor articles.
    Downstream (``load_retrieved_article_texts``) dedups to articles and loads full
    markdown, so a neighbor only needs its article name as the doc_id.
    """

    def __init__(
        self,
        db: Chroma,
        graph: WikiGraph,
        params: GraphParams | None = None,
        top_k: int = DEFAULT_TOP_K,
        label: str | None = None,
    ):
        super().__init__(top_k=top_k, label=label or "vector_graph")
        self._db = db
        self.graph = graph
        self.params = params or GraphParams()

    def _seed(self, query: str, k: int) -> tuple[list[tuple[str, str, float]], list[str]]:
        results = self._db.similarity_search_with_score(query, k=k)
        sims = normalize_scores([distance for _, distance in results], invert=True)
        hits: list[tuple[str, str, float]] = []
        seed_articles: list[str] = []
        seen: set[str] = set()
        for (doc, _), sim in zip(results, sims):
            doc_id = doc.metadata.get("source", "unknown")
            hits.append((doc_id, doc.page_content, sim))
            article = doc_id.split("#", 1)[0]
            if article not in seen:
                seen.add(article)
                seed_articles.append(article)
        return hits, seed_articles

    def retrieve_verbose(self, query: str, k: int | None = None) -> dict[str, Any]:
        """Seeds + neighbors (with reasons) — for logging and the smoke test."""
        k = self.top_k if k is None else k
        seed_hits, seed_articles = self._seed(query, k)
        neighbors = self.graph.expand(seed_articles, self.params)
        return {"seed_articles": seed_articles, "neighbors": neighbors, "seed_hits": seed_hits}

    def article_sections(
        self, query: str, article: str, k: int
    ) -> list[tuple[str, str]]:
        """Top-k chunks of a SINGLE article, ranked by similarity to the query
        (metadata-filtered vector search over the chunk index). Returns
        ``(section_label, text)`` pairs. Lets a graph neighbor contribute its most
        query-relevant sections — the second stage of two-stage retrieval (graph
        finds the article, vector search finds the section) — instead of a fixed
        char slice of its lead."""
        if k <= 0:
            return []
        results = self._db.similarity_search_with_score(
            query, k=k, filter={"article": article}
        )
        sections: list[tuple[str, str]] = []
        for doc, _distance in results:
            label = (
                doc.metadata.get("section_title")
                or doc.metadata.get("section_path")
                or ""
            )
            sections.append((label, doc.page_content))
        return sections

    def getTopK(self, query: str, k: int | None = None) -> list[tuple[str, str, float]]:
        k = self.top_k if k is None else k
        seed_hits, seed_articles = self._seed(query, k)
        seen = set(seed_articles)
        hits = list(seed_hits)
        for article, score, _reasons in self.graph.expand(seed_articles, self.params):
            if article in seen:
                continue
            seen.add(article)
            hits.append((article, "", score))  # content unused: eval reloads full markdown
        return hits

    def settings(self) -> dict[str, Any]:
        return {
            "kind": "vector_graph",
            "label": self.label,
            "top_k": self.top_k,
            **self.params.as_dict(),
        }
