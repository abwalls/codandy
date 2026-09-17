import io
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.debugging import sentry_client
from app.routers import debugging
from tests.test_debugging import config


def transport(monkeypatch, rows, link=""):
    calls = []
    def open_request(request, timeout):
        calls.append(request.full_url)
        assert timeout == 5
        response = io.BytesIO(json.dumps(rows).encode())
        response.headers = {"Link": link}
        return response
    monkeypatch.setattr(sentry_client, "build_opener", lambda *args: SimpleNamespace(open=open_request))
    return calls


def test_projects_are_bounded_scrubbed_and_ignore_pagination_hosts(monkeypatch):
    rows = [{"id": "7", "name": "test_token password=secret", "slug": "demo", "members": [{"email": "private@example.test"}]}]
    calls = transport(monkeypatch, rows, '<https://evil.example/private>; rel="next"; results="true"; cursor="0:50:0"')
    result = sentry_client.browse(config(), "projects", query="demo")
    assert "private" not in json.dumps(result)
    assert "secret" not in result["items"][0]["name"]
    assert "test_token" not in result["items"][0]["name"]
    assert result["next_cursor"] == "0:50:0"
    sentry_client.browse(config(), "projects", cursor=result["next_cursor"])
    assert len(calls) == 2 and all(url.startswith("https://sentry.io/api/0/organizations/example/projects/?") for url in calls)
    assert parse_qs(urlsplit(calls[-1]).query)["per_page"] == ["50"]


def test_issue_search_keeps_project_scope_and_narrow_fields(monkeypatch):
    rows = [{"id": "123", "title": "Error", "culprit": "f", "status": "unresolved", "project": {"id": "7"}, "assignedTo": {"email": "private@example.test"}}]
    calls = transport(monkeypatch, rows)
    result = sentry_client.browse(config(), "issues", project="7", query="is:unresolved")
    assert set(result["items"][0]) == {"id", "title", "culprit", "status"}
    assert parse_qs(urlsplit(calls[0]).query)["shortIdLookup"] == ["0"]
    with pytest.raises(sentry_client.SentryError, match="unsupported listing"):
        sentry_client.browse(config(), "issues", project="8")


@pytest.mark.parametrize("options", [{"cursor": "https://evil.test"}, {"cursor": "0:2:9"}, {"query": "x"*301}, {"query": "a\nb"}])
def test_browse_rejects_bad_inputs_before_network(monkeypatch, options):
    monkeypatch.setattr(sentry_client, "_fetch", lambda *args: pytest.fail("must not send"))
    with pytest.raises(sentry_client.SentryError):
        sentry_client.browse(config(), "projects", **options)


def test_unsupported_more_cursor_is_visible_and_large_pages_rejected(monkeypatch):
    transport(monkeypatch, [], '<https://sentry.io>; rel="next"; results="true"; cursor="opaque"')
    result = sentry_client.browse(config(), "projects")
    assert result["next_cursor"] is None
    assert any("unsupported" in note for note in result["notes"])
    transport(monkeypatch, [{"id": str(i)} for i in range(51)])
    with pytest.raises(sentry_client.SentryError, match="unsupported listing"):
        sentry_client.browse(config(), "projects")


def test_browse_api_local_only_and_explicit(monkeypatch):
    calls = []
    monkeypatch.setattr(debugging, "browse", lambda *args, **kw: calls.append((args, kw)) or {"items": [], "next_cursor": None, "notes": []})
    app = FastAPI(); app.include_router(debugging.router, prefix="/api")
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 123)) as client:
        headers = {"X-Codandy-Local": "1"}
        assert client.get("/api/debugging/sentry/projects").status_code == 403
        assert calls == []
        assert client.get("/api/debugging/sentry/projects", headers=headers).status_code == 200
        assert client.get("/api/debugging/sentry/issues?project=7", headers=headers).status_code == 200
        assert len(calls) == 2
        assert client.get("/api/debugging/sentry/issues?project=../bad", headers=headers).status_code == 422
