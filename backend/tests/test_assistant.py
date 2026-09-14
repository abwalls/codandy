import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.analyzer import analyze_repository
from app.codex_bridge import CodexBridge
from app.routers.assistant import Question, grounded_prompt, router
from app.settings import Settings


def test_codex_turn_uses_supported_read_only_policy_and_disposes_ephemeral_context(tmp_path):
    bridge = CodexBridge("unused", tmp_path)
    calls = []
    closed = []

    def rpc(method, params, timeout=25):
        calls.append((method, params))
        if method == "thread/start":
            return {"thread": {"id": "thread-1"}}
        assert method == "turn/start"
        bridge.events.extend([
            {"method": "item/completed", "params": {"threadId": "thread-1",
                "item": {"type": "agentMessage", "text": '{"answer":"A declaration.","citations":[]}'}}},
            {"method": "turn/completed", "params": {"threadId": "thread-1",
                "turn": {"id": "turn-1", "status": "completed"}}},
        ])
        return {"turn": {"id": "turn-1"}}

    bridge.rpc = rpc
    bridge.close = lambda: closed.append(True)
    assert bridge.answer("Explain this declaration", "test-model", "low")["answer"] == "A declaration."
    assert calls[0][1]["ephemeral"] is True
    assert calls[0][1]["approvalPolicy"] == "never"
    assert calls[1][1]["sandboxPolicy"] == {"type": "readOnly", "networkAccess": False}
    assert calls[1][1]["outputSchema"]["additionalProperties"] is False
    assert closed == [True]


@pytest.fixture
def assistant_client(tmp_path):
    (tmp_path / "app.py").write_text("def example(): pass\n")
    atlas = analyze_repository(tmp_path, "https://github.com/org/repo.git", None, Settings(), lambda *_: None)
    job_id = uuid4()
    app = FastAPI()
    app.include_router(router, prefix="/api")
    bridge = SimpleNamespace(lock=threading.Lock(), account=lambda: {"connected": True, "plan": "pro"},
        models=lambda: [{"id": "test-model", "name": "Test", "default": True, "default_effort": "low", "efforts": ["low"]}],
        answer=lambda *_: {"answer": "A syntax declaration is indexed.", "citations": []})
    app.state.codex = bridge
    app.state.jobs = SimpleNamespace(result=lambda value: atlas if value == job_id else None)
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 12345)) as client:
        yield client, bridge, atlas, job_id


def test_connection_requires_local_header_and_origin(assistant_client):
    client, _, _, _ = assistant_client
    path = "/api/analyses/assistant/status"
    assert client.get(path).status_code == 403
    assert client.get(path, headers={"X-Codandy-Local": "1", "Origin": "https://attacker.example"}).status_code == 403
    assert client.get(path, headers={"X-Codandy-Local": "1", "Host": "attacker.example"}).status_code == 403
    result = client.get(path, headers={"X-Codandy-Local": "1", "Origin": "http://localhost:5173"})
    assert result.status_code == 200
    assert result.json()["connected"]


def test_answers_require_valid_model_scope_and_citations(assistant_client):
    client, bridge, atlas, job_id = assistant_client
    selected = next(node.id for node in atlas.nodes if node.kind == "function")
    data = {"analysis_id": str(job_id), "question": "What is a symbol?", "model": "test-model", "effort": "low", "node_ids": [selected]}
    headers = {"X-Codandy-Local": "1"}
    path = "/api/analyses/assistant/ask"
    assert client.post(path, json=data, headers=headers).status_code == 200
    assert client.post(path, json={**data, "model": "invented"}, headers=headers).status_code == 422
    assert client.post(path, json={**data, "effort": "max"}, headers=headers).status_code == 422
    assert client.post(path, json={**data, "node_ids": ["invented"]}, headers=headers).status_code == 422
    bridge.answer = lambda *_: {"answer": "Invented citation", "citations": ["invented"]}
    assert client.post(path, json=data, headers=headers).status_code == 502
    bridge.account = lambda: {"connected": False, "plan": None}
    assert client.post(path, json=data, headers=headers).status_code == 409


def test_context_is_bounded_and_not_arbitrary_client_source(assistant_client):
    _, _, atlas, job_id = assistant_client
    selected = next(node.id for node in atlas.nodes if node.kind == "function")
    question = Question(analysis_id=job_id, question="Explain", model="test", effort="low", node_ids=[selected])
    prompt, included = grounded_prompt(atlas, question)
    assert included == {selected}
    assert "def example(): pass" not in prompt
    question.node_ids = ["missing"]
    with pytest.raises(HTTPException):
        grounded_prompt(atlas, question)


def test_busy_bridge_does_not_start_another_request(assistant_client):
    client, bridge, _, _ = assistant_client
    bridge.lock.acquire()
    try:
        assert client.get("/api/analyses/assistant/status", headers={"X-Codandy-Local": "1"}).status_code == 409
    finally:
        bridge.lock.release()


def test_login_accepts_only_official_openai_signin(assistant_client):
    client, bridge, _, _ = assistant_client
    bridge.start = lambda: None
    bridge.rpc = lambda *_: {"authUrl": "https://attacker.example/steal"}
    headers = {"X-Codandy-Local": "1"}
    assert client.post("/api/analyses/assistant/login", headers=headers).status_code == 503
    bridge.rpc = lambda *_: {"authUrl": "https://auth.openai.com/oauth/authorize?state=example"}
    assert client.post("/api/analyses/assistant/login", headers=headers).json()["url"].startswith("https://auth.openai.com/")


def test_question_rejects_arbitrary_context_and_blank_input(assistant_client):
    client, _, _, job_id = assistant_client
    data = {"analysis_id": str(job_id), "question": " ", "model": "test-model", "effort": "low"}
    headers = {"X-Codandy-Local": "1"}
    assert client.post("/api/analyses/assistant/ask", headers=headers, json=data).status_code == 422
    assert client.post("/api/analyses/assistant/ask", headers=headers, json={**data, "question": "Explain", "source": "untrusted extra"}).status_code == 422
