import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.integrations import linear
from app.integrations.tickets import Draft, Submission, TicketConflict, TicketStore, review
from app.main import app
from app.settings import Settings, settings

TEAM = "11111111-1111-4111-8111-111111111111"
ISSUE = "22222222-2222-4222-8222-222222222222"
HEADERS = {"X-Codandy-Local": "1"}


def config():
    return Settings(linear_api_key=SecretStr("lin_api_test_credential"))


def draft():
    return Draft(team_id=TEAM, title="Investigate checkout", description="User plan: add regression coverage")


def submission(cfg, value=None):
    value = value or draft()
    return Submission(**value.model_dump(), digest=review(cfg, value)["digest"],
                      idempotency_key=uuid4(), confirmed=True)


def receipt(*args):
    return {"external_id": ISSUE, "external_key": "DEMO-1", "url": "https://linear.app/issue/DEMO-1"}


def test_review_scrubs_secrets_and_binds_content_target_and_account():
    cfg = config()
    value = draft().model_copy(update={"description": "password=secret " + cfg.linear_api_key.get_secret_value()})
    packet = review(cfg, value)
    assert "secret" not in packet["payload"]["description"]
    assert "lin_api" not in packet["payload"]["description"]
    for change in ({"title": "Different"}, {"team_id": uuid4()}, {"source_id": "different"}):
        assert review(cfg, value.model_copy(update=change))["digest"] != packet["digest"]
    assert review(Settings(linear_api_key=SecretStr("other")), value)["digest"] != packet["digest"]


def test_idempotent_receipt_survives_restart_without_ticket_body(tmp_path, monkeypatch):
    cfg = config()
    submitted = submission(cfg)
    calls = []
    monkeypatch.setattr(linear, "create_issue", lambda *a: calls.append(a) or receipt())
    store = TicketStore(tmp_path)
    first = store.submit(cfg, submitted)
    again = TicketStore(tmp_path).submit(cfg, submitted.model_copy(update={"idempotency_key": uuid4()}))
    assert first == again
    assert len(calls) == 1
    assert b"User plan" not in store.path.read_bytes()
    assert b"credential" not in store.path.read_bytes()
    assert store.history()["items"][0]["state"] == "created"


def test_uncertain_submission_is_never_sent_twice(tmp_path, monkeypatch):
    calls = []
    def fail(*args):
        calls.append(1)
        raise linear.ProviderError("Connection lost")
    monkeypatch.setattr(linear, "create_issue", fail)
    cfg, submitted = config(), submission(config())
    with pytest.raises(linear.ProviderError):
        TicketStore(tmp_path).submit(cfg, submitted)
    with pytest.raises(TicketConflict, match="may already exist"):
        TicketStore(tmp_path).submit(cfg, submitted)
    assert calls == [1]
    assert TicketStore(tmp_path).history()["items"][0]["state"] == "uncertain"


def test_stale_digest_and_reused_key_are_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(linear, "create_issue", receipt)
    cfg, submitted = config(), submission(config())
    store = TicketStore(tmp_path)
    with pytest.raises(TicketConflict, match="changed"):
        store.submit(cfg, submitted.model_copy(update={"title": "changed"}))
    store.submit(cfg, submitted)
    other = submission(cfg, draft().model_copy(update={"title": "other"}))
    with pytest.raises(TicketConflict, match="different reviewed"):
        store.submit(cfg, other.model_copy(update={"idempotency_key": submitted.idempotency_key}))


def test_no_persistence_blocks_creation(monkeypatch):
    monkeypatch.setattr(linear, "create_issue", lambda *a: pytest.fail("must not send"))
    with pytest.raises(TicketConflict, match="Enable"):
        TicketStore(None).submit(config(), submission(config()))


def test_ticket_api_local_review_create_and_history(monkeypatch):
    monkeypatch.setattr(settings, "linear_api_key", config().linear_api_key)
    monkeypatch.setattr(linear, "create_issue", receipt)
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 123)) as client:
        assert client.get("/api/integrations").status_code == 403
        assert client.get("/api/integrations", headers={**HEADERS, "Origin": "https://bad.example"}).status_code == 403
        status = client.get("/api/integrations", headers=HEADERS)
        assert status.json()["configured"]
        assert "credential" not in status.text
        raw = draft().model_dump(mode="json")
        packet = client.post("/api/integrations/tickets/review", json=raw, headers=HEADERS).json()
        data = {**raw, "digest": packet["digest"], "idempotency_key": str(uuid4()), "confirmed": True}
        assert client.post("/api/integrations/tickets", json={**data, "confirmed": False}, headers=HEADERS).status_code == 422
        result = client.post("/api/integrations/tickets", json=data, headers=HEADERS)
        assert result.status_code == 200
        assert result.json()["external_key"] == "DEMO-1"
        assert client.get("/api/integrations/tickets", headers=HEADERS).json()["items"][0]["state"] == "created"
        assert client.post("/api/integrations/tickets/review", content=b"x"*100001,
                           headers={**HEADERS, "Content-Type": "application/json"}).status_code == 413


class Response:
    def __init__(self, data):
        self.data = data
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read1(self, size):
        chunk, self.data = self.data[:size], self.data[size:]
        return chunk


def transport(monkeypatch, payload):
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://api.linear.app/graphql"
            assert request.headers["Authorization"] == "lin_api_test_credential"
            assert timeout == 5
            return Response(payload)
    monkeypatch.setattr(linear, "build_opener", lambda *args: Opener())


@pytest.mark.parametrize("payload", [b"bad", b'{"data":{},"errors":[{"message":"token secret"}]}', b"x"*2097153], ids=["malformed", "graphql-error", "oversized"])
def test_provider_failures_do_not_echo_response(monkeypatch, payload):
    transport(monkeypatch, payload)
    with pytest.raises(linear.ProviderError) as error:
        linear.test_connection(config())
    assert "token secret" not in str(error.value)


def test_linear_reads_and_create_validate_provider_contracts(monkeypatch):
    transport(monkeypatch, json.dumps({"data": {"teams": {"nodes": [{"id": TEAM, "name": "Test"}], "pageInfo": {"hasNextPage": True}}}}).encode())
    assert linear.teams(config())["has_more"] is True
    transport(monkeypatch, json.dumps({"data": {"issueCreate": {"success": True, "issue": {"id": ISSUE, "identifier": "DEMO-1"}}}}).encode())
    assert linear.create_issue(config(), {}) == receipt()


def test_credentials_reject_header_injection():
    with pytest.raises(linear.ProviderError):
        linear.key(Settings(linear_api_key=SecretStr("token\r\nInjected: yes")))

@pytest.mark.parametrize("code", [302, 401, 403, 429, 500])
def test_http_errors_are_sanitized_and_never_retried(monkeypatch, code):
    from urllib.error import HTTPError
    calls = []
    class Opener:
        def open(self, request, timeout):
            calls.append(1)
            raise HTTPError(request.full_url, code, "private response lin_api_test_credential", {}, None)
    monkeypatch.setattr(linear, "build_opener", lambda *args: Opener())
    with pytest.raises(linear.ProviderError) as error:
        linear.query(config(), "query { viewer { id } }")
    assert "credential" not in str(error.value)
    assert calls == [1]


def test_transport_disables_proxies_and_redirects(monkeypatch):
    from urllib.request import ProxyHandler
    handlers = []
    class Opener:
        def open(self, request, timeout):
            return Response(b'{"data":{"viewer":{"id":"test"}}}')
    def capture(*args):
        handlers.extend(args)
        return Opener()
    monkeypatch.setattr(linear, "build_opener", capture)
    linear.test_connection(config())
    assert any(isinstance(h, ProxyHandler) and h.proxies == {} for h in handlers)
    redirect = next(h for h in handlers if isinstance(h, linear.NoRedirect))
    assert redirect.redirect_request(None, None, 302, "", {}, "https://evil.example") is None
