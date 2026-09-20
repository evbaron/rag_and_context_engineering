"""Build once and read normalized Wikipedia table artifacts at agent runtime.

The builder is an offline preprocessing step. It parses every source article, writes
one compressed artifact per article, and atomically publishes a manifest only after
all artifacts succeed. ``TableArtifactStore`` is intentionally read-only: agent
nodes can locate and load artifacts, but cannot silently mutate the corpus cache.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from wikipedia_retrieval_engine.utils.wiki_table_parser import (
    DEFAULT_TABLE_SELECTOR,
    PARSER_VERSION,
    NormalizedTable,
    parse_wikipedia_file,
)


STORE_SCHEMA_VERSION = 1
ENGINE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WIKI_DIR = ENGINE_ROOT / "Wikipedia Library"
DEFAULT_TABLE_STORE_DIR = (
    ENGINE_ROOT / "retrievers" / "db" / "table_artifacts" / "wikipedia_tables"
)


class SourceFileStamp(BaseModel):
    """Cheap rebuild check; the source SHA-256 is stored in the artifact itself."""

    size: int = Field(ge=0)
    mtime_ns: int = Field(ge=0)


class TableCatalogEntry(BaseModel):
    artifact_id: str
    source_article: str
    table_id: str
    table_role: str
    caption: str | None
    section_path: list[str]
    columns: list[str]
    row_count: int = Field(ge=0)
    legend_meanings: list[str] = Field(default_factory=list)


class ArticleManifestEntry(BaseModel):
    source_article: str
    artifact_file: str
    source_hash: str
    table_count: int = Field(ge=0)
    stamp: SourceFileStamp


class TableArtifactManifest(BaseModel):
    schema_version: int
    parser_version: str
    table_selector: str
    built_at: str
    source_directory: str
    article_count: int = Field(ge=0)
    table_count: int = Field(ge=0)
    articles: dict[str, ArticleManifestEntry]
    catalog: list[TableCatalogEntry]


class TableArtifactStore:
    """Lazy, read-only access to precomputed normalized table artifacts."""

    def __init__(self, root: Path, manifest: TableArtifactManifest) -> None:
        self.root = root
        self.manifest = manifest
        self._catalog_by_artifact = {
            entry.artifact_id: entry for entry in manifest.catalog
        }

    @classmethod
    def open(cls, root: str | Path = DEFAULT_TABLE_STORE_DIR) -> "TableArtifactStore":
        store_root = Path(root)
        manifest_path = store_root / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"Table artifact manifest not found: {manifest_path}. "
                "Run the offline wiki_table_store builder first."
            )
        try:
            manifest = TableArtifactManifest.model_validate_json(
                manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError, ValueError) as error:
            raise RuntimeError(f"Invalid table artifact manifest: {manifest_path}") from error

        if manifest.schema_version != STORE_SCHEMA_VERSION:
            raise RuntimeError(
                "Table artifact schema mismatch: "
                f"store={manifest.schema_version}, code={STORE_SCHEMA_VERSION}. Rebuild the store."
            )
        if manifest.parser_version != PARSER_VERSION:
            raise RuntimeError(
                "Table parser version mismatch: "
                f"store={manifest.parser_version}, code={PARSER_VERSION}. Rebuild the store."
            )
        return cls(store_root, manifest)

    def __len__(self) -> int:
        return self.manifest.table_count

    def has_article(self, source_article: str) -> bool:
        return source_article in self.manifest.articles

    def list_articles(self) -> list[str]:
        return sorted(self.manifest.articles)

    def list_tables(
        self,
        source_article: str | None = None,
        *,
        include_legends: bool = False,
    ) -> list[TableCatalogEntry]:
        return [
            entry
            for entry in self.manifest.catalog
            if (source_article is None or entry.source_article == source_article)
            and (include_legends or entry.table_role != "legend")
        ]

    def find_tables(
        self,
        query: str,
        *,
        source_article: str | None = None,
        include_legends: bool = False,
        limit: int = 10,
    ) -> list[TableCatalogEntry]:
        """Rank catalog metadata by deterministic query-token overlap."""

        if limit < 1:
            return []
        query_tokens = _search_tokens(query)
        ranked: list[tuple[int, int, TableCatalogEntry]] = []
        for position, entry in enumerate(
            self.list_tables(source_article, include_legends=include_legends)
        ):
            haystack = " ".join(
                [
                    entry.source_article,
                    entry.caption or "",
                    *entry.section_path,
                    *entry.columns,
                    *entry.legend_meanings,
                ]
            )
            score = len(query_tokens & _search_tokens(haystack))
            if not query_tokens or score:
                ranked.append((score, -position, entry))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _, _, entry in ranked[:limit]]

    def load_article(self, source_article: str) -> list[NormalizedTable]:
        entry = self.manifest.articles.get(source_article)
        if entry is None:
            raise KeyError(f"No table artifact exists for article: {source_article}")
        artifact_path = _safe_artifact_path(self.root, entry.artifact_file)
        if not artifact_path.is_file():
            raise FileNotFoundError(
                f"Table artifact is missing for {source_article}: {artifact_path}"
            )
        with gzip.open(artifact_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("schema_version") != STORE_SCHEMA_VERSION:
            raise RuntimeError(f"Artifact schema mismatch: {artifact_path}")
        if payload.get("parser_version") != PARSER_VERSION:
            raise RuntimeError(f"Artifact parser version mismatch: {artifact_path}")
        if payload.get("source_article") != source_article:
            raise RuntimeError(f"Artifact/source mismatch: {artifact_path}")
        if payload.get("source_hash") != entry.source_hash:
            raise RuntimeError(f"Artifact hash does not match manifest: {artifact_path}")
        return [NormalizedTable.model_validate(table) for table in payload["tables"]]

    def load_table(self, source_article: str, table_id: str) -> NormalizedTable:
        for table in self.load_article(source_article):
            if table.table_id == table_id:
                return table
        raise KeyError(f"Table {table_id!r} is not present in {source_article}")

    def load_artifact(self, artifact_id: str) -> NormalizedTable:
        catalog_entry = self._catalog_by_artifact.get(artifact_id)
        if catalog_entry is None:
            raise KeyError(f"Unknown table artifact ID: {artifact_id}")
        return self.load_table(catalog_entry.source_article, catalog_entry.table_id)


def _search_tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"\w+", value.casefold()) if len(token) > 1}


def _source_inventory(html_paths: list[Path]) -> dict[str, SourceFileStamp]:
    return {
        path.name: SourceFileStamp(
            size=path.stat().st_size,
            mtime_ns=path.stat().st_mtime_ns,
        )
        for path in html_paths
    }


def _artifact_filename(
    source_article: str,
    source_hash: str,
    table_selector: str,
) -> str:
    """Return an immutable, content- and parser-addressed artifact path."""

    identity = "\0".join(
        [
            source_article,
            source_hash,
            table_selector,
            PARSER_VERSION,
            str(STORE_SCHEMA_VERSION),
        ]
    )
    digest = hashlib.sha256(identity.encode()).hexdigest()
    return f"articles/{digest}.json.gz"


def _safe_artifact_path(root: Path, relative_path: str) -> Path:
    root_resolved = root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root_resolved):
        raise RuntimeError(f"Unsafe artifact path in manifest: {relative_path}")
    return path


def _write_json_gzip_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(temporary, "wt", encoding="utf-8", compresslevel=6) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    temporary.replace(path)


def _write_manifest_atomic(path: Path, manifest: TableArtifactManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_manifest_if_current(
    root: Path,
    *,
    wiki_dir: Path,
    table_selector: str,
    inventory: dict[str, SourceFileStamp],
) -> TableArtifactManifest | None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = TableArtifactManifest.model_validate_json(
            manifest_path.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError, ValueError):
        return None
    expected = {
        name: stamp.model_dump(mode="json") for name, stamp in inventory.items()
    }
    actual = {
        name: entry.stamp.model_dump(mode="json")
        for name, entry in manifest.articles.items()
    }
    artifacts_exist = all(
        _safe_artifact_path(root, entry.artifact_file).is_file()
        for entry in manifest.articles.values()
    )
    if (
        manifest.schema_version == STORE_SCHEMA_VERSION
        and manifest.parser_version == PARSER_VERSION
        and manifest.table_selector == table_selector
        and Path(manifest.source_directory) == wiki_dir.resolve()
        and expected == actual
        and artifacts_exist
    ):
        return manifest
    return None


def build_table_artifact_store(
    wiki_dir: str | Path = DEFAULT_WIKI_DIR,
    output_dir: str | Path = DEFAULT_TABLE_STORE_DIR,
    *,
    table_selector: str = DEFAULT_TABLE_SELECTOR,
    force: bool = False,
) -> TableArtifactStore:
    """Build the complete persistent artifact store, or reuse a valid build."""

    source_root = Path(wiki_dir).resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"Wikipedia HTML directory not found: {source_root}")
    html_paths = sorted(
        path
        for path in source_root.iterdir()
        if path.suffix.casefold() == ".html" and not path.name.startswith("_")
    )
    if not html_paths:
        raise ValueError(f"No Wikipedia HTML files found in {source_root}")

    store_root = Path(output_dir)
    inventory = _source_inventory(html_paths)
    if not force:
        current = _load_manifest_if_current(
            store_root,
            wiki_dir=source_root,
            table_selector=table_selector,
            inventory=inventory,
        )
        if current is not None:
            print(
                f"Loading existing table artifact store from {store_root}/ "
                f"({current.article_count} articles, {current.table_count} tables)"
            )
            return TableArtifactStore(store_root, current)

    articles: dict[str, ArticleManifestEntry] = {}
    catalog: list[TableCatalogEntry] = []
    print(f"Building table artifacts for {len(html_paths)} Wikipedia articles...")
    for number, html_path in enumerate(html_paths, 1):
        tables = parse_wikipedia_file(html_path, table_selector=table_selector)
        source_hash = (
            tables[0].source_hash
            if tables
            else hashlib.sha256(html_path.read_bytes()).hexdigest()
        )
        relative_artifact = _artifact_filename(
            html_path.name,
            source_hash,
            table_selector,
        )
        artifact_path = _safe_artifact_path(store_root, relative_artifact)
        payload = {
            "schema_version": STORE_SCHEMA_VERSION,
            "parser_version": PARSER_VERSION,
            "source_article": html_path.name,
            "source_hash": source_hash,
            "tables": [table.model_dump(mode="json") for table in tables],
        }
        _write_json_gzip_atomic(artifact_path, payload)
        articles[html_path.name] = ArticleManifestEntry(
            source_article=html_path.name,
            artifact_file=relative_artifact,
            source_hash=source_hash,
            table_count=len(tables),
            stamp=inventory[html_path.name],
        )
        catalog.extend(
            TableCatalogEntry(
                artifact_id=table.artifact_id,
                source_article=table.source_article,
                table_id=table.table_id,
                table_role=table.table_role,
                caption=table.caption,
                section_path=table.section_path,
                columns=table.columns,
                row_count=len(table.rows),
                legend_meanings=[legend.meaning for legend in table.legends],
            )
            for table in tables
        )
        if number % 100 == 0 or number == len(html_paths):
            print(f"  parsed {number}/{len(html_paths)} articles ({len(catalog)} tables)")

    manifest = TableArtifactManifest(
        schema_version=STORE_SCHEMA_VERSION,
        parser_version=PARSER_VERSION,
        table_selector=table_selector,
        built_at=datetime.now(timezone.utc).isoformat(),
        source_directory=str(source_root),
        article_count=len(articles),
        table_count=len(catalog),
        articles=articles,
        catalog=catalog,
    )
    _write_manifest_atomic(store_root / "manifest.json", manifest)
    print(
        f"Published table artifact manifest: {len(articles)} articles, "
        f"{len(catalog)} tables -> {store_root}/"
    )
    return TableArtifactStore(store_root, manifest)


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the read-only normalized Wikipedia table artifact store."
    )
    parser.add_argument("--wiki-dir", type=Path, default=DEFAULT_WIKI_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_TABLE_STORE_DIR)
    parser.add_argument("--table-selector", default=DEFAULT_TABLE_SELECTOR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    build_table_artifact_store(
        wiki_dir=args.wiki_dir,
        output_dir=args.output_dir,
        table_selector=args.table_selector,
        force=args.force,
    )


if __name__ == "__main__":
    _main()
