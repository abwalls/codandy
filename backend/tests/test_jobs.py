import json
import threading
import time
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app import jobs
from app.ingestion import IngestionError
from app.main import app
from app.models import AtlasDocument


def wait_for_terminal(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/analyses/{job_id}")
        assert response.status_code == 200
        if response.json()["status"] in {"complete", "failed"}:
            return response.json()
        time.sleep(0.01)
    pytest.fail("Job did not finish")


@pytest.fixture
def repository(tmp_path, monkeypatch):
    (tmp_path / "index.ts").write_text('export function run() {}')
    (tmp_path / ".git" / "refs" / "heads").mkdir(parents=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (tmp_path / ".git" / "refs" / "heads" / "main").write_text("a" * 40)
    state = {"exited": False}

    @contextmanager
    def clone(*_):
        try:
            yield tmp_path
        finally:
            state["exited"] = True

    monkeypatch.setattr(jobs, "clone_repository", clone)
    return tmp_path, state


def submit(client):
    response = client.post("/api/analyses", json={"source": {
        "url": "https://github.com/org/repo", "ref": "main"}})
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    return response.json()["id"]


def test_complete_artifact_and_sse_replay(repository):
    root, state = repository
    with TestClient(app) as client:
        job_id = submit(client)
        assert wait_for_terminal(client, job_id)["status"] == "complete"
        response = client.get(f"/api/analyses/{job_id}/atlas")
        assert response.status_code == 200
        atlas = AtlasDocument.model_validate(response.json())
        assert atlas.repository["commit"] == "a" * 40
        assert atlas.repository["branch"] == "main"
        assert state["exited"]
        assert AtlasDocument.model_validate_json(
            (root / ".codandy" / "atlas.json").read_text(encoding="utf-8")) == atlas
        events = client.get(f"/api/analyses/{job_id}/events")
        assert events.headers["content-type"].startswith("text/event-stream")
        blocks = events.text.strip().split("\n\n")
        snapshots = [json.loads(block.split("data: ", 1)[1]) for block in blocks]
        assert snapshots[0]["status"] == "queued"
        assert snapshots[-1]["status"] == "complete"
        assert [s["progress"] for s in snapshots] == sorted(s["progress"] for s in snapshots)
        replay = client.get(f"/api/analyses/{job_id}/events", headers={"Last-Event-ID": "2"})
        assert replay.text.strip().split("\n\n") == blocks[2:]
        assert client.get(f"/api/analyses/{job_id}/events",
                          headers={"Last-Event-ID": "-1"}).status_code == 422


@pytest.mark.parametrize("error", [IngestionError("Repository exceeds graph node limit"),
                                  RuntimeError("sensitive internal detail")])
def test_failed_job_and_workspace_exit(repository, monkeypatch, error):
    def fail(*_):
        raise error

    monkeypatch.setattr(jobs, "analyze_repository", fail)
    with TestClient(app) as client:
        job_id = submit(client)
        terminal = wait_for_terminal(client, job_id)
        assert terminal["status"] == "failed"
        assert "sensitive internal detail" not in terminal["error"]
        assert repository[1]["exited"]
        assert client.get(f"/api/analyses/{job_id}/atlas").status_code == 409
        stream = client.get(f"/api/analyses/{job_id}/events").text
        assert json.loads(stream.strip().split("data: ")[-1])["status"] == "failed"


def test_busy_not_ready_and_retention(repository, monkeypatch):
    original = jobs.analyze_repository
    release = threading.Event()

    def paused(*args):
        if not release.wait(timeout=5):
            raise RuntimeError("Test release timed out")
        return original(*args)

    monkeypatch.setattr(jobs, "analyze_repository", paused)
    with TestClient(app) as client:
        app.state.jobs.limits = app.state.jobs.limits.model_copy(update={"max_jobs": 1})
        first = submit(client)
        try:
            assert client.get(f"/api/analyses/{first}/atlas").status_code == 409
            assert client.delete(f"/api/analyses/{first}").status_code == 409
            busy = client.post("/api/analyses", json={"source": {
                "url": "https://github.com/org/repo"}})
            assert busy.status_code == 429
            assert busy.headers["Retry-After"] == "5"
        finally:
            release.set()
        assert wait_for_terminal(client, first)["status"] == "complete"
        second = submit(client)
        assert wait_for_terminal(client, second)["status"] == "complete"
        assert client.get(f"/api/analyses/{first}").status_code == 404
        assert client.get(f"/api/analyses/{first}/events").status_code == 404


def test_source_endpoint_serves_only_captured_paths(repository):
    with TestClient(app) as client:
        job_id = submit(client)
        assert wait_for_terminal(client, job_id)["status"] == "complete"
        response = client.get(f"/api/analyses/{job_id}/source", params={"path": "index.ts"})
        assert response.status_code == 200
        body = response.json()
        assert body["path"] == "index.ts"
        assert "export function run()" in body["text"]
        assert body["truncated"] is False
        # Unindexed, traversal and absolute paths are not addressable at all.
        for path in ["missing.ts", "../../../etc/passwd", "/etc/passwd", ".git/HEAD",
                     "C:/Windows/win.ini"]:
            denied = client.get(f"/api/analyses/{job_id}/source", params={"path": path})
            assert denied.status_code == 404, path
        assert client.get(f"/api/analyses/{job_id}/source").status_code == 422
        unknown = "00000000-0000-4000-8000-000000000000"
        assert client.get(f"/api/analyses/{unknown}/source",
                          params={"path": "index.ts"}).status_code == 404


def test_source_is_evicted_with_the_report(repository):
    with TestClient(app) as client:
        job_id = submit(client)
        assert wait_for_terminal(client, job_id)["status"] == "complete"
        store = app.state.jobs
        assert job_id in {str(key) for key in store.sources}
        store.jobs.clear()
        store.events.clear()
        store.results.clear()
        store.sources.clear()
        assert client.get(f"/api/analyses/{job_id}/source",
                          params={"path": "index.ts"}).status_code == 404


def test_completed_job_is_persisted_and_reopened_after_restart(repository, monkeypatch, tmp_path):
    from app.main import settings

    monkeypatch.setattr(settings, "report_root", str(tmp_path / "saved-reports"))
    with TestClient(app) as client:
        job_id = submit(client)
        assert wait_for_terminal(client, job_id)["status"] == "complete"
        assert client.get("/api/analyses").json()["persistent"] is True
        original = client.get(f"/api/analyses/{job_id}/atlas").json()
    with TestClient(app) as client:
        history = client.get("/api/analyses").json()
        assert history["reports"][0]["id"] == job_id
        assert client.get(f"/api/analyses/{job_id}/atlas").json() == original
        assert client.get(f"/api/analyses/{job_id}/source", params={"path": "index.ts"}).status_code == 200
        assert "complete" in client.get(f"/api/analyses/{job_id}/events").text


def test_remove_report_deletes_persisted_source_and_survives_restart(repository, monkeypatch, tmp_path):
    from app.main import settings

    monkeypatch.setattr(settings, "report_root", str(tmp_path / "saved-reports"))
    with TestClient(app) as client:
        job_id = submit(client)
        assert wait_for_terminal(client, job_id)["status"] == "complete"
        assert client.delete(f"/api/analyses/{job_id}").json() == {"deleted": job_id}
        assert client.get("/api/analyses").json()["reports"] == []
        assert client.get(f"/api/analyses/{job_id}/source", params={"path": "index.ts"}).status_code == 404
        assert client.delete(f"/api/analyses/{job_id}").status_code == 404
    with TestClient(app) as client:
        assert client.get(f"/api/analyses/{job_id}").status_code == 404


def test_dependency_check_requires_a_real_dependency_node(repository, monkeypatch):
    from app.routers import analyses

    (repository[0] / "package.json").write_text('{"dependencies":{"lodash":"4.17.20"}}')
    seen = []

    def checked(node):
        seen.append(node.id)
        return {"node_id": node.id}

    monkeypatch.setattr(analyses, "check_dependency", checked)
    with TestClient(app) as client:
        job_id = submit(client)
        assert wait_for_terminal(client, job_id)["status"] == "complete"
        atlas = client.get(f"/api/analyses/{job_id}/atlas").json()
        dependency = next(node for node in atlas["nodes"] if node["kind"] == "dependency")
        result = client.post(f"/api/analyses/{job_id}/dependencies", params={"node_id": dependency["id"]})
        assert result.status_code == 200
        assert seen == [dependency["id"]]
        assert client.post(f"/api/analyses/{job_id}/dependencies", params={"node_id": "invented"}).status_code == 404
        assert client.post(f"/api/analyses/{job_id}/dependencies").status_code == 422
        assert seen == [dependency["id"]]
