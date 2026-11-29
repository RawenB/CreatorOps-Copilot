"""Tests for the settings module."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from creatorops import __version__
from creatorops.config import Settings, get_settings


def test_package_has_version() -> None:
    assert __version__


def test_defaults_are_local_and_derived_paths_filled(tmp_path: Path) -> None:
    settings = Settings(_env_file=None, data_dir=tmp_path)

    assert settings.llm_provider == "ollama"
    assert settings.qdrant_mode == "local"
    assert settings.manifest_path == tmp_path / "manifest.csv"
    assert settings.db_path == tmp_path / "creatorops.sqlite"
    assert settings.qdrant_path == tmp_path / "qdrant"


def test_env_vars_override_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CREATOROPS_LLM_PROVIDER", "fake")
    monkeypatch.setenv("CREATOROPS_SQL_ROW_LIMIT", "50")
    monkeypatch.setenv("CREATOROPS_DB_PATH", str(tmp_path / "x.sqlite"))

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "fake"
    assert settings.sql_row_limit == 50
    assert settings.db_path == tmp_path / "x.sqlite"


def test_invalid_values_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CREATOROPS_LLM_PROVIDER", "not-a-provider")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
