import copy
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.debugging.payload import NormalizationError
from app.debugging.traces import normalize_trace_bytes
from app.routers.debugging import router


def fixture():
    return {"resourceSpans": [{"resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "checkout"}}]},
                              "scopeSpans": [{"spans": [
                                  {"traceId": "A" * 32, "spanId": "1" * 16, "name": "checkout", "startTimeUnixNano": "1700000000000000001", "endTimeUnixNano": "1700000000100000001"},
                                  {"traceId": "a" * 32, "spanId": "2" * 16, "parentSpanId": "1" * 16, "name": "password=sentinel-secret", "startTimeUnixNano": "1700000000000000002", "endTimeUnixNano": "1700000000080000000", "status": {"code": 2}, "attributes": [{"key": "db.statement", "value": {"stringValue": "PRIVATE_SQL"}}, {"key": "code.file.path", "value": {"stringValue": "/home/someone/app.py"}}]},
                              ]}]}]}


def normalize(value):
    return normalize_trace_bytes(json.dumps(value).encode())


def test_trace_precision_parentage_and_scrubbing():
    trace = normalize(fixture())
    assert trace.spans[0].start_ns == "1700000000000000001"
    assert trace.spans[1].parent_state == "present"
    assert trace.spans[1].trace_id == "a" * 32
    assert trace.spans[1].status == "error"
    for secret in ("sentinel-secret", "PRIVATE_SQL", "someone"):
        assert secret not in trace.model_dump_json()
    assert trace.withheld_attributes == 1 and trace.redactions


@pytest.mark.parametrize("field,value", [("traceId", "0" * 32), ("spanId", "base64!"), ("startTimeUnixNano", -1), ("endTimeUnixNano", "1"), ("startTimeUnixNano", "9" * 20), ("status", {"code": "STATUS_CODE_ERROR"})])
def test_bad_span_fields_rejected(field, value):
    payload = fixture()
    payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0][field] = value
    with pytest.raises(NormalizationError):
        normalize(payload)


def test_orphans_cycles_and_duplicates_are_visible():
    payload = fixture()
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    spans[0]["parentSpanId"] = "f" * 16
    assert normalize(payload).spans[0].parent_state == "missing"
    spans[0]["parentSpanId"] = "2" * 16
    assert all(s.parent_state == "cycle" for s in normalize(payload).spans)
    spans.append(copy.deepcopy(spans[0]))
    with pytest.raises(NormalizationError, match="Duplicate"):
        normalize(payload)


def test_span_budget_reports_omissions():
    payload = fixture()
    original = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    payload["resourceSpans"][0]["scopeSpans"][0]["spans"] = [{**original, "spanId": f"{i:016x}"} for i in range(1, 1003)]
    result = normalize(payload)
    assert len(result.spans) == 1000 and result.omitted_spans == 2


def test_trace_api_boundaries():
    app = FastAPI(); app.include_router(router, prefix="/api")
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 123)) as client:
        path = "/api/debugging/traces/import"
        headers = {"X-Codandy-Local": "1"}
        assert client.post(path, json=fixture()).status_code == 403
        assert client.post(path, json=fixture(), headers={**headers, "Origin": "https://evil.test"}).status_code == 403
        assert client.post(path, content="{}", headers=headers).status_code == 415
        assert client.post(path, json=fixture(), headers=headers).status_code == 200
        assert client.post(path, content='{"resourceSpans":[],"resourceSpans":[]}', headers={**headers, "Content-Type": "application/json"}).status_code == 422
        assert client.post(path, content=b"x" * (2 * 1024 * 1024 + 1), headers={**headers, "Content-Type": "application/json"}).status_code == 413
