import os
import time

import pytest

from app.ingestion import IngestionError
from app.settings import Settings
from app.worker import analyze_isolated


def hang(*_):
    time.sleep(30)


def crash(*_):
    os._exit(7)


def test_real_isolated_parser(tmp_path):
    (tmp_path / "index.ts").write_text("export function run() {}")
    (tmp_path / "schema.sql").write_text("CREATE TABLE users (id int PRIMARY KEY);")
    atlas, structure = analyze_isolated(tmp_path, "https://github.com/org/repo.git", None,
                                        Settings(), lambda *_: None)
    assert atlas.counts["symbols"] == 1
    assert [entity.table for entity in structure.entities] == ["users"]


@pytest.mark.parametrize(("worker", "message"), [(hang, "timed out"),
                                                  (crash, "exited unexpectedly")])
def test_worker_timeout_and_crash(tmp_path, worker, message):
    start = time.monotonic()
    with pytest.raises(IngestionError, match=message):
        analyze_isolated(tmp_path, "https://github.com/org/repo.git", None,
                         Settings(analysis_timeout_seconds=2), lambda *_: None, worker=worker)
    assert time.monotonic() - start < 10


def atlas_then_stall(connection, root, url, ref, limits):
    from pathlib import Path

    from app.analyzer import analyze_repository
    atlas = analyze_repository(Path(root), url, ref, Settings.model_validate(limits), lambda *_: None)
    connection.send(("atlas", atlas.model_dump_json()))
    time.sleep(30)


def test_optional_structure_timeout_preserves_completed_atlas(tmp_path):
    (tmp_path / "index.ts").write_text("export function run() {}")
    atlas, structure = analyze_isolated(tmp_path, "https://github.com/org/repo.git", None,
                                        Settings(analysis_timeout_seconds=2), lambda *_: None,
                                        worker=atlas_then_stall)
    assert atlas.counts["symbols"] == 1
    assert structure.limitations
