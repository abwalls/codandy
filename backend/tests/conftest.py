"""Tests must never use the developer's reports, investigations, or provider credentials."""

import pytest
from pydantic import SecretStr


@pytest.fixture(autouse=True)
def isolate_application_storage(tmp_path, monkeypatch):
    from app.main import settings
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "report_root", None)
    monkeypatch.setattr(settings, "investigation_root", str(tmp_path / "investigations"))
    monkeypatch.setattr(settings, "codex_enabled", False)
    monkeypatch.setattr(settings, "codex_home", str(tmp_path / "codex"))
    monkeypatch.setattr(settings, "sentry_token", SecretStr(""))
    monkeypatch.setattr(settings, "sentry_organization", "")
