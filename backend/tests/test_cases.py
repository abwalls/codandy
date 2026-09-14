import json
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.debugging.cases import CaseStore
from app.debugging.stacks import normalize_stack_text
from app.routers import cases, debugging


def observation():
    return normalize_stack_text("Error: password=hunter2\n at fail (/app/main.js:3:1)")


def test_save_restart_update_delete(tmp_path):
    store = CaseStore(tmp_path)
    imported = store.remember(observation())
    saved = store.save(imported.id)
    assert store.save(imported.id).id == saved.id
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert "hunter2" not in next(tmp_path.glob("*.json")).read_text()
    reopened = CaseStore(tmp_path)
    assert reopened.get(saved.id) == saved
    updated = reopened.update(saved.id, "Investigate customer@example.com", "resolved", "password=hunter2")
    assert "customer@example.com" not in updated.title
    assert "hunter2" not in updated.notes
    assert updated.state == "resolved"
    assert updated.observation == saved.observation
    assert CaseStore(tmp_path).get(saved.id) == updated
    reopened.delete(saved.id)
    assert not CaseStore(tmp_path).listing()["cases"]


def test_failed_write_leaves_memory_unchanged(tmp_path, monkeypatch):
    store = CaseStore(tmp_path)
    saved = store.save(store.remember(observation()).id)
    def fail(*args):
        raise OSError("disk full")
    monkeypatch.setattr("app.debugging.cases.os.replace", fail)
    with pytest.raises(OSError):
        store.update(saved.id, "Changed", "open", "notes")
    assert store.get(saved.id) == saved
    assert not list(tmp_path.glob("*.tmp"))
    assert CaseStore(tmp_path).get(saved.id) == saved


def test_case_copies_cannot_mutate_stored_evidence():
    store = CaseStore(None)
    imported = store.remember(observation())
    original_title = imported.title
    imported.title = "tampered"
    saved = store.save(imported.id)
    assert saved.observation.title == original_title
    saved.observation.title = "tampered again"
    assert store.get(saved.id).observation.title == original_title


def test_unknown_ids_and_pending_eviction():
    store = CaseStore(None)
    first = store.remember(observation())
    for _ in range(20):
        store.remember(observation())
    with pytest.raises(KeyError):
        store.save(first.id)
    with pytest.raises(KeyError):
        store.get(uuid4())


def test_corrupt_and_wrong_identity_files_preserved(tmp_path):
    corrupt = tmp_path / f"{uuid4()}.json"
    corrupt.write_text("not json")
    store = CaseStore(tmp_path)
    saved = store.save(store.remember(observation()).id)
    wrong = tmp_path / f"{uuid4()}.json"
    wrong.write_text(saved.model_dump_json())
    restored = CaseStore(tmp_path)
    assert restored.listing()["unreadable"] == 2
    assert len(restored.listing()["cases"]) == 1
    assert corrupt.exists() and wrong.exists()


def test_case_api_only_saves_server_normalized_observation(tmp_path):
    app = FastAPI()
    app.state.investigations = CaseStore(tmp_path)
    app.include_router(debugging.router, prefix="/api")
    app.include_router(cases.router, prefix="/api")
    headers = {"X-Codandy-Local": "1"}
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1234)) as api:
        obs = api.post("/api/debugging/imports", content="Error: failed\n at f (/a.js:1:1)",
                       headers={**headers, "Content-Type": "text/plain"}).json()
        saved = api.post("/api/debugging/cases", json={"observation_id": obs["id"]}, headers=headers)
        assert saved.status_code == 200
        path = f'/api/debugging/cases/{saved.json()["id"]}'
        assert api.get(path, headers=headers).json()["observation"] == obs
        assert api.get(path).status_code == 403
        assert api.post("/api/debugging/cases", json={"observation_id": str(uuid4()), "observation": obs}, headers=headers).status_code == 422
        updated = api.put(path, json={"title": "Check", "state": "resolved", "notes": "token=secret"}, headers=headers)
        assert updated.status_code == 200
        assert "secret" not in updated.json()["notes"]
        assert api.delete(path, headers=headers).status_code == 204
        assert api.get(path, headers=headers).status_code == 404
        assert api.get("/api/debugging/cases", headers=headers).json()["cases"] == []
        assert all("token=secret" not in json.dumps(x) for x in app.state.investigations.cases.values())
