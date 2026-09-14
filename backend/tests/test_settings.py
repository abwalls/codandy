from app.settings import Settings


def test_codandy_environment_supports_legacy_installations(monkeypatch):
    monkeypatch.setenv("CODE_ATLAS_REPORT_ROOT", "existing-reports")
    assert Settings(_env_file=None).report_root == "existing-reports"
    monkeypatch.setenv("CODANDY_REPORT_ROOT", "new-reports")
    assert Settings(_env_file=None).report_root == "new-reports"


def test_legacy_dotenv_and_new_names(tmp_path):
    env = tmp_path / ".env"
    env.write_text("CODE_ATLAS_CODEX_ENABLED=true\nCODE_ATLAS_REPORT_ROOT=old\nCODANDY_REPORT_ROOT=new\n")
    settings = Settings(_env_file=env)
    assert settings.codex_enabled
    assert settings.report_root == "new"
