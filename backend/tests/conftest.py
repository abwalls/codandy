"""Tests must never use the developer's reports, investigations, or provider credentials."""

import os

import pytest
from pydantic import SecretStr

from app.settings import Settings


@pytest.fixture(autouse=True)
def isolate_application_storage(tmp_path, monkeypatch):
    # Settings() instances created inside tests must not read backend/.env or CODANDY_*
    # variables either. Patching only the shared object left that path open: a JobStore
    # built from a fresh Settings() loaded, and could evict, personal reports.
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for name in list(os.environ):
        if name.upper().startswith(("CODANDY_", "CODE_ATLAS_")):
            monkeypatch.delenv(name)
    from app.main import settings
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "report_root", None)
    monkeypatch.setattr(settings, "board_root", str(tmp_path / "boards"))
    monkeypatch.setattr(settings, "investigation_root", str(tmp_path / "investigations"))
    monkeypatch.setattr(settings, "codex_enabled", False)
    monkeypatch.setattr(settings, "codex_home", str(tmp_path / "codex"))
    monkeypatch.setattr(settings, "integration_root", str(tmp_path / "integrations"))
    monkeypatch.setattr(settings, "linear_api_key", SecretStr(""))
    monkeypatch.setattr(settings, "sentry_token", SecretStr(""))
    monkeypatch.setattr(settings, "sentry_organization", "")
    # TestClient sends Host: testserver; the application itself allows only local names.
    monkeypatch.setattr(settings, "allowed_hosts", ["localhost", "127.0.0.1", "::1", "testserver"])
