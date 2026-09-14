import json

import pytest

from app.analyzer import analyze_repository
from app.jobs import JobStore
from app.models import AnalysisJob, SourceFile
from app.report_storage import ReportStorage, Snapshot
from app.settings import Settings


def snapshot(tmp_path):
    source = tmp_path / "source"
    source.mkdir(exist_ok=True)
    (source / "index.ts").write_text("export function run() {}")
    atlas = analyze_repository(source, "https://github.com/org/repo.git", None,
                               Settings(), lambda *_: None)
    job = AnalysisJob(status="complete", phase="complete", progress=100)
    return Snapshot(job=job, atlas=atlas,
                    sources={"index.ts": SourceFile(path="index.ts", text="source", lines=1,
                                                    truncated=False)},
                    events=[job.model_dump_json()])


def test_restart_restores_reports_source_and_terminal_events(tmp_path):
    saved = snapshot(tmp_path)
    storage = ReportStorage(str(tmp_path / "reports"))
    storage.save(saved)
    jobs = JobStore(Settings(report_root=str(storage.root)))
    try:
        assert jobs.result(saved.job.id) == saved.atlas
        assert jobs.source(saved.job.id, "index.ts") == saved.sources["index.ts"]
        assert jobs.read_events(saved.job.id, 0) == (saved.events, True)
        assert jobs.recent()[0]["id"] == str(saved.job.id)
    finally:
        jobs.close()
    assert not list(storage.root.glob("*.tmp"))


def test_corrupt_or_mismatched_snapshots_are_not_restored(tmp_path):
    saved = snapshot(tmp_path)
    storage = ReportStorage(str(tmp_path / "reports"))
    storage.save(saved)
    path = storage.root / f"{saved.job.id}.json"
    path.write_text("not JSON")
    assert storage.load(10) == []
    payload = saved.model_dump(mode="json")
    payload["sources"]["../secret"] = payload["sources"].pop("index.ts")
    path.write_text(json.dumps(payload))
    assert storage.load(10) == []


def test_retention_removes_old_completed_snapshots(tmp_path):
    saved = snapshot(tmp_path)
    storage = ReportStorage(str(tmp_path / "reports"))
    storage.save(saved)
    newer = saved.model_copy(update={"job": AnalysisJob(status="complete", phase="complete", progress=100)})
    newer.events = [newer.job.model_dump_json()]
    storage.save(newer)
    # Ensure timestamp ordering even on low-resolution filesystems.
    import os
    os.utime(storage.root / f"{saved.job.id}.json", (1, 1))
    assert [entry.job.id for entry in storage.load(1)] == [newer.job.id]
    assert not (storage.root / f"{saved.job.id}.json").exists()


def test_failed_atomic_replace_preserves_previous_snapshot(tmp_path, monkeypatch):
    from app import report_storage

    saved = snapshot(tmp_path)
    storage = ReportStorage(str(tmp_path / "reports"))
    storage.save(saved)
    previous = (storage.root / f"{saved.job.id}.json").read_bytes()

    def fail(*args):
        raise OSError("disk unavailable")

    monkeypatch.setattr(report_storage.os, "replace", fail)
    with pytest.raises(OSError):
        storage.save(saved)
    assert (storage.root / f"{saved.job.id}.json").read_bytes() == previous
    assert not list(storage.root.glob("*.tmp"))
