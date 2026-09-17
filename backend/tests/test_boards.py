import json
import threading
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.boards import (
    Artifact,
    BoardStore,
    Conflict,
    Draft,
    Edit,
    Interpretation,
    Plan,
    Scene,
    packet,
    render_plan,
    validate_output,
)
from app.routers.board_routes import router


def scene():
    return Scene(elements=[{"id": "api", "type": "rectangle", "x": 0, "y": 0, "width": 100, "height": 70},
                           {"id": "label", "type": "text", "x": 4, "y": 4, "text": "API token=supersecret", "containerId": "api"},
                           {"id": "arrow", "type": "arrow", "startBinding": {"elementId": "api"}, "endBinding": None}])


def interpretation():
    return Interpretation(summary="Proposed API", findings=[{"text": "API", "element_ids": ["api"], "basis": "drawn"}], questions=["Who can call it?"], assumptions=[])


def test_store_conflicts_restart_delete_and_immutable_reads(tmp_path):
    store = BoardStore(tmp_path)
    board = store.create(Draft(scene=scene()))
    copy = store.get(board.id)
    copy.scene.elements.clear()
    assert store.get(board.id).scene.elements
    updated = store.update(board.id, Edit(revision=1, title="Design", scene=scene()))
    assert updated.revision == 2
    with pytest.raises(Conflict):
        store.update(board.id, Edit(revision=1))
    restored = BoardStore(tmp_path)
    assert restored.get(board.id).title == "Design"
    with pytest.raises(Conflict):
        restored.delete(board.id, 1)
    restored.delete(board.id, 2)
    assert not BoardStore(tmp_path).items


def test_failed_write_preserves_memory_and_file(tmp_path, monkeypatch):
    import app.boards as module
    store = BoardStore(tmp_path)
    board = store.create(Draft(title="Before"))
    def fail(*args):
        raise OSError("full disk")
    monkeypatch.setattr(module.os, "replace", fail)
    with pytest.raises(OSError):
        store.update(board.id, Edit(revision=1, title="After"))
    assert store.get(board.id).title == "Before"
    assert BoardStore(tmp_path).get(board.id).title == "Before"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("element", [
    {"id": "a", "type": "image"}, {"id": "a", "type": "embeddable"},
    {"id": "a", "type": "text", "text": "x" * 2001},
    {"id": "a", "type": "rectangle", "x": float("nan")},
    {"id": "a", "type": "rectangle", "link": "https://example.com"},
    {"id": "a", "type": "arrow", "startBinding": "invalid"},
])
def test_unsafe_elements_rejected(element):
    with pytest.raises(ValueError):
        Scene(elements=[element])


def test_digest_redaction_order_dangling_and_stale_review():
    store = BoardStore(None)
    board = store.create(Draft(scene=scene()))
    review = packet(board, "interpret")
    assert "supersecret" not in review["text"]
    assert next(e for e in review["packet"]["elements"] if e["id"] == "arrow")["ends"] == ["api", None]
    board.scene.elements.reverse()
    assert packet(board, "interpret")["digest"] == review["digest"]
    board.notes = "Use private access"
    assert packet(board, "interpret")["digest"] != review["digest"]
    with pytest.raises(ValueError):
        packet(board, "plan")


def test_output_citations_and_dependency_cycles_rejected():
    board = BoardStore(None).create(Draft(scene=scene()))
    review = packet(board, "interpret")
    value = interpretation()
    assert validate_output(value, review) == value
    value.findings[0].element_ids = ["invented"]
    with pytest.raises(ValueError):
        validate_output(value, review)
    value.findings[0].element_ids = []
    with pytest.raises(ValueError):
        validate_output(value, review)


def test_api_local_boundary_stale_reviews_and_mock_generation():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.boards = BoardStore(None)
    app.state.jobs = SimpleNamespace(result=lambda _: None)
    calls = []
    def complete(*args):
        calls.append(args)
        return interpretation().model_dump()
    app.state.codex = SimpleNamespace(lock=threading.Lock(), account=lambda: {"connected": True},
                                     models=lambda: [{"id": "test", "efforts": ["low"]}], complete=complete)
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1234)) as client:
        assert client.get("/api/boards").status_code == 403
        headers = {"X-Codandy-Local": "1"}
        board = client.post("/api/boards", json={"scene": scene().model_dump()}, headers=headers).json()
        path = f"/api/boards/{board['id']}"
        review = client.get(path + "/review", headers=headers).json()
        payload = {"stage": "interpret", "digest": review["digest"], "model": "test", "effort": "low"}
        assert client.post(path + "/generate", json=payload, headers=headers).status_code == 200
        assert len(calls) == 1
        assert "supersecret" not in json.dumps(calls)
        assert client.put(path, json={"revision": 1, "notes": "Changed"}, headers=headers).status_code == 200
        assert client.post(path + "/generate", json=payload, headers=headers).status_code == 409
        assert len(calls) == 1
        assert client.get(path, headers={**headers, "Origin": "https://evil.example"}).status_code == 403


def test_stale_artifact_rejected_and_old_plan_export_marked():
    store = BoardStore(None)
    board = store.create(Draft())
    store.update(board.id, Edit(revision=1))
    with pytest.raises(Conflict):
        store.add_artifact(board.id, Artifact(revision=1, stage="interpret", digest="x", model="test", interpretation=interpretation()))
    plan = Plan(title="Feature", objective="Build it", in_scope=[], out_of_scope=[], decisions=[],
                tasks=[{"id": "one", "title": "Implement", "description": "Do work", "depends_on": [],
                        "acceptance_criteria": ["Works"], "verification": ["Check behavior"], "proposed_paths": []}],
                risks=[], open_questions=[])
    artifact = Artifact(revision=1, stage="plan", digest="x", model="test", plan=plan)
    assert "STALE" in render_plan(store.get(board.id), artifact)
    plan.tasks[0].depends_on = ["one"]
    with pytest.raises(ValueError):
        validate_output(plan, packet(board, "interpret"))


def test_reading_guide_and_group_context_exclude_deleted_labels():
    drawing = scene()
    drawing.elements += [{"id": "pen", "type": "freedraw", "groupIds": ["proposal"]},
                         {"id": "unlabeled", "type": "ellipse", "frameId": "missing"},
                         {"id": "deleted", "type": "text", "text": "Ignored", "containerId": "unlabeled", "isDeleted": True}]
    board = BoardStore(None).create(Draft(scene=drawing))
    review = packet(board, "interpret")
    assert review["reading_guide"] == {"included_elements": 5, "omitted_elements": 0,
                                       "freehand_elements": 1, "unbound_connectors": 1, "unlabeled_shapes": 1}
    records = {v["id"]: v for v in review["packet"]["elements"]}
    assert records["pen"]["groups"] == ["proposal"]
    assert records["unlabeled"]["frame"] is None
    assert "deleted" not in records


def test_plan_outputs_include_structured_tasks_and_preserve_stale_state():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.boards = BoardStore(None)
    board = app.state.boards.create(Draft())
    plan = Plan(title="Feature", objective="Build it", in_scope=[], out_of_scope=[], decisions=[],
                tasks=[{"id": "one", "title": "Implement", "description": "Do work", "depends_on": [],
                        "acceptance_criteria": ["Works"], "verification": ["Check behavior"], "proposed_paths": []}],
                risks=[], open_questions=[])
    artifact = Artifact(revision=1, stage="plan", digest="x", model="test", plan=plan)
    app.state.boards.add_artifact(board.id, artifact)
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1234)) as client:
        path = f"/api/boards/{board.id}/outputs/{artifact.id}"
        assert client.get(path).status_code == 403
        value = client.get(path, headers={"X-Codandy-Local": "1"}).json()
        assert value["structured_plan"] == plan.model_dump()
        assert value["artifact_id"] == str(artifact.id)
        assert value["revision"] == 1 and not value["stale"]
        app.state.boards.update(board.id, Edit(revision=1, notes="Change goal"))
        stale = client.get(path, headers={"X-Codandy-Local": "1"}).json()
        assert stale["stale"] and "STALE" in stale["plan"]
        assert stale["structured_plan"] == value["structured_plan"]
