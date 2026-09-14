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


def test_new_settings_in_tests_cannot_inherit_personal_storage_or_credentials():
    # conftest.py must cover Settings() instances created inside tests, not only the shared
    # app settings object; stores built from them would load and evict personal reports.
    fresh = Settings()
    assert fresh.report_root is None
    assert not fresh.sentry_token.get_secret_value()
    assert not fresh.sentry_organization
    assert not fresh.codex_enabled
