import gzip
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.debugging import sentry_client
from app.debugging.models import DebuggingLimits
from app.debugging.payload import NormalizationError, load_json
from app.debugging.redaction import Redactor
from app.debugging.sentry_event import normalize_sentry_event, normalize_sentry_event_bytes
from app.debugging.stacks import normalize_stack_text
from app.routers.debugging import router

FIXTURES = Path(__file__).parent / "fixtures" / "debugging"


def fixture():
    return json.loads((FIXTURES / "sentry_python_chained.json").read_text())


def test_sentry_normalization_scrubs_sensitive_sections_and_preserves_chain():
    result = normalize_sentry_event(fixture())
    serialized = result.model_dump_json()
    for secret in ("customer@example.com", "hunter2", "sk_live_abcdefghijklmnop1234", "203.0.113.10"):
        assert secret not in serialized
    assert result.exceptions[0].relation_to_next == "direct_cause"
    assert result.exceptions[-1].frames[-1].path == "app/db.py"
    assert result.exceptions[-1].frames[-1].line == 14
    assert "user" in result.withheld
    assert "frame.vars" in result.withheld
    assert result.redactions


def test_missing_source_maps_never_fetch_urls():
    result = normalize_sentry_event_bytes((FIXTURES / "sentry_javascript_minified.json").read_bytes())
    assert "127.0.0.1" not in result.model_dump_json()
    assert "frame.mapUrl" in result.withheld
    assert any(note.type == "js_no_source" for note in result.provider_notes)


def test_limits_keep_recent_failure_with_visible_truncation():
    result = normalize_sentry_event(fixture(), DebuggingLimits(max_frames=1, max_breadcrumbs=0, max_context_lines=0))
    assert sum(len(e.frames) for e in result.exceptions) == 1
    assert result.exceptions[-1].frames[-1].line == 14
    assert not result.breadcrumbs
    assert result.truncations


def test_partially_identified_chain_does_not_invent_relationships():
    payload = fixture()
    values = payload["entries"][0]["data"]["values"]
    values[0]["mechanism"] = {"exception_id": 1}
    values[1]["mechanism"] = {}
    assert normalize_sentry_event(payload).exceptions[0].relation_to_next is None


@pytest.mark.parametrize("payload", [b'{"a": NaN}', b'{"a": Infinity}', b'{"x":1,"x":2}', b'\xff', b'[' * 33 + b']' * 33])
def test_bad_json_is_rejected(payload):
    with pytest.raises(NormalizationError):
        load_json(payload, DebuggingLimits())


def test_gzip_expansion_and_trailing_data_are_bounded():
    limits = DebuggingLimits(max_payload_bytes=1024)
    assert load_json(gzip.compress(b'{}'), limits) == {}
    for data in (gzip.compress(b' ' * 2000), gzip.compress(b'{}') + b'extra', gzip.compress(b'{}')[:-2]):
        with pytest.raises(NormalizationError):
            load_json(data, limits)


@pytest.mark.parametrize("text,secret", [('Authorization: Bearer abc', 'abc'), ('{"password":"hunter2"}', 'hunter2'), ('api_key=sk_live_abcdefghijklmnop1234', 'abcdefghijklmnop'), ('C:\\Users\\someone\\app.py', 'someone')])
def test_redaction(text, secret):
    assert secret not in Redactor().text(text, "test")


def test_python_chained_stack_and_redaction():
    text = '''Traceback (most recent call last):
  File "app.py", line 4, in inner
    fail()
ValueError: password=hunter2

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "main.py", line 9, in outer
    inner()
RuntimeError: failed
'''
    result = normalize_stack_text(text)
    assert result.exceptions[0].type == "ValueError"
    assert result.exceptions[0].relation_to_next == "direct_cause"
    assert result.exceptions[1].frames[0].line == 9
    assert "hunter2" not in result.model_dump_json()


def test_javascript_cause_frames_are_not_merged():
    result = normalize_stack_text('Error: outer\n    at fail (/app/fail.js:3:4)\n    at main (/app/main.js:9:2)\n  [cause]: Error: inner\n    at secret (/app/inner.js:1:1)')
    assert [f.function for f in result.exceptions[0].frames] == ["main", "fail"]
    assert any("not interpreted" in note for note in result.limitations)


def test_firefox_stack_order():
    result = normalize_stack_text('TypeError: failed\nfail@https://example.com/app.js:3:8\nmain@https://example.com/app.js:9:1')
    assert [f.line for f in result.exceptions[0].frames] == [9, 3]


def test_dotnet_inner_and_async_frames():
    result = normalize_stack_text('''System.InvalidOperationException: outer ---> System.ArgumentException: inner
   at App.Service.Fail() in C:\\repo\\Service.cs:line 8
   --- End of inner exception stack trace ---
   at App.Controller.Run() in C:\\repo\\Controller.cs:line 20
   --- End of stack trace from previous location ---
   at App.Program.Main()
''')
    assert [e.type for e in result.exceptions] == ["System.ArgumentException", "System.InvalidOperationException"]
    assert result.exceptions[0].frames[0].line == 8
    assert result.exceptions[0].relation_to_next == "inner_exception"
    assert result.exceptions[1].frames[-1].after_async_boundary
    assert result.exceptions[1].frames[0].path is None


def test_overlong_stack_lines_rejected_before_parsing():
    with pytest.raises(NormalizationError, match="Stack lines"):
        normalize_stack_text('Error: password="' + 'x' * 4096 + '"\n at f (/a.js:1:1)')


@pytest.mark.parametrize("payload", [{"event_id": "abc", "exception": {}}, {"entries": []}, []])
def test_unsupported_sentry_shapes(payload):
    with pytest.raises(NormalizationError):
        normalize_sentry_event(payload)


def config():
    return SimpleNamespace(sentry_host="sentry.io", sentry_organization="example",
                           sentry_token=SecretStr("test_token"))


def test_sentry_reads_only_explicit_event(monkeypatch):
    calls = []
    def open_request(request, timeout):
        calls.append(request)
        assert timeout == 5
        assert request.get_header("Authorization") == "Bearer test_token"
        return io.BytesIO(json.dumps(fixture()).encode())
    monkeypatch.setattr(sentry_client, "build_opener", lambda *args: SimpleNamespace(open=open_request))
    result = sentry_client.fetch_event(config(), "4501", "latest")
    assert len(calls) == 1
    assert calls[0].full_url == "https://sentry.io/api/0/organizations/example/issues/4501/events/latest/"
    assert result.source.fetched_at is not None


@pytest.mark.parametrize("code", [301, 401, 403, 404, 429, 500])
def test_sentry_errors_do_not_echo_response_or_token(monkeypatch, code):
    def fail(*args, **kwargs):
        raise HTTPError("https://sentry.io", code, "SECRET_PROVIDER_MESSAGE", {}, io.BytesIO(b"SECRET_BODY"))
    monkeypatch.setattr(sentry_client, "build_opener", lambda *args: SimpleNamespace(open=fail))
    with pytest.raises(sentry_client.SentryError) as caught:
        sentry_client.fetch_event(config(), "4501", "latest")
    assert "SECRET" not in str(caught.value)
    assert "test_token" not in str(caught.value)


@pytest.mark.parametrize("issue,event", [("../secret", "latest"), ("4501", "http://127.0.0.1"), ("4501", "../latest")])
def test_sentry_request_validation(issue, event):
    with pytest.raises(sentry_client.SentryError):
        sentry_client.fetch_event(config(), issue, event)


def test_sentry_no_redirect():
    assert sentry_client.NoRedirect().redirect_request(None, None, 302, "", {}, "http://localhost") is None


def client(host="127.0.0.1"):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return TestClient(app, base_url="http://localhost", client=(host, 1234))


def test_import_api_and_boundary():
    with client() as api:
        path = "/api/debugging/imports"
        assert api.post(path, content="abc").status_code == 403
        headers = {"X-Codandy-Local": "1", "Content-Type": "application/json"}
        response = api.post(path, content=json.dumps(fixture()), headers=headers)
        assert response.status_code == 200
        assert response.json()["schema_version"] == "debugging-0.1"
        assert api.post(path, content="{}", headers={**headers, "Origin": "https://attacker.example"}).status_code == 403
        assert api.post(path, content="x" * (2 * 1024 * 1024 + 1), headers=headers).status_code == 413
        assert api.post(path, content="{}", headers=headers).status_code == 422
    with client("203.0.113.1") as api:
        assert api.get("/api/debugging/sentry/status", headers={"X-Codandy-Local": "1"}).status_code == 403


def test_sentry_oversize_response_rejected(monkeypatch):
    monkeypatch.setattr(sentry_client, "build_opener", lambda *args: SimpleNamespace(
        open=lambda *args, **kwargs: io.BytesIO(b"x" * (2 * 1024 * 1024 + 1))))
    with pytest.raises(sentry_client.SentryError, match="budget"):
        sentry_client.fetch_event(config(), "4501", "latest")


def test_sentry_wrong_event_rejected(monkeypatch):
    monkeypatch.setattr(sentry_client, "build_opener", lambda *args: SimpleNamespace(
        open=lambda *args, **kwargs: io.BytesIO(json.dumps(fixture()).encode())))
    with pytest.raises(sentry_client.SentryError, match="different event"):
        sentry_client.fetch_event(config(), "4501", "a" * 32)


def test_sentry_timeout_is_safe(monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError("sensitive transport details")
    monkeypatch.setattr(sentry_client, "build_opener", lambda *args: SimpleNamespace(open=fail))
    with pytest.raises(sentry_client.SentryError, match="timeout"):
        sentry_client.fetch_event(config(), "4501", "latest")
