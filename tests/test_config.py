from creatorops.config import Settings


def test_default_settings():
    s = Settings(_env_file=None)
    assert s.llm_provider == "ollama"
    assert s.db_path.name == "creatorops.sqlite"


def test_env_variable_overrides_default(monkeypatch):
    monkeypatch.setenv("CREATOROPS_LLM_PROVIDER", "fake")
    monkeypatch.setenv("CREATOROPS_SQL_MAX_ROWS", "50")
    s = Settings(_env_file=None)
    assert s.llm_provider == "fake"
    assert s.sql_max_rows == 50
