import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.debugging.brief import build_brief
from app.debugging.cases import CaseStore
from app.debugging.stacks import normalize_stack_text
from app.routers.cases import router


def saved_case():
    store = CaseStore(None)
    obs = normalize_stack_text("Error: password=hunter2\n" + "\n".join(f" at f{i} (/src/app.js:{i + 1}:2)" for i in range(50)))
    saved = store.save(store.remember(obs).id)
    return store, store.update(saved.id, "Review failure", "open", "password=secret\nTry checking the input")


def test_brief_is_bounded_cited_and_separates_user_notes():
    _, case = saved_case()
    brief = build_brief(case)
    assert brief["included_frames"] == 24
    assert brief["omitted_frames"] == 26
    assert len(brief["prompt"].encode()) < 64000
    assert "hunter2" not in brief["prompt"]
    assert "password=secret" not in brief["prompt"]
    assert brief["packet"]["user_notes"]["basis"] == "user_annotation_not_verified"
    ids = [item["id"] for item in brief["packet"]["evidence"]]
    assert len(ids) == len(set(ids))
    assert all(str(case.observation.id) in key for key in ids)
    assert build_brief(case)["review_digest"] == brief["review_digest"]


def test_brief_digest_changes_when_saved_evidence_changes():
    store, case = saved_case()
    old = build_brief(case)
    updated = store.update(case.id, "Changed title", "open", case.notes)
    assert build_brief(updated)["review_digest"] != old["review_digest"]


def test_case_ai_requires_current_review_and_valid_citations():
    store, case = saved_case()
    packet = build_brief(case)
    citation = packet["packet"]["evidence"][0]["id"]
    calls = []
    def answer(prompt, model, effort):
        calls.append(prompt)
        return {"answer": "Check the failing input; cause is not verified.", "citations": [citation]}
    bridge = SimpleNamespace(lock=threading.Lock(), account=lambda: {"connected": True},
        models=lambda: [{"id": "test-model", "efforts": ["low"]}], answer=answer)
    app = FastAPI()
    app.state.investigations = store
    app.state.codex = bridge
    app.include_router(router, prefix="/api")
    headers = {"X-Codandy-Local": "1"}
    body = {"question": "Explain token=private", "model": "test-model", "effort": "low", "review_digest": packet["review_digest"]}
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1234)) as api:
        path = f"/api/debugging/cases/{case.id}/ask"
        assert api.post(path, json=body).status_code == 403
        assert api.post(path, json={**body, "review_digest": "0" * 64}, headers=headers).status_code == 409
        assert not calls
        assert api.post(path, json=body, headers=headers).status_code == 200
        assert "token=private" not in calls[-1]
        bridge.answer = lambda *args: {"answer": "Invented", "citations": ["not-in-packet"]}
        assert api.post(path, json=body, headers=headers).status_code == 502
        store.update(case.id, "New title", "open", "Changed notes")
        assert api.post(path, json=body, headers=headers).status_code == 409
