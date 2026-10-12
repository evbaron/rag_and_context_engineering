"""Shared test setup. Tests never call a real model or embedding API."""

import pytest


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Every test writes logs and reports to its own temporary folder."""
    monkeypatch.setenv("RAG_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test-key-not-used")
    yield
