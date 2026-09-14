import asyncio
import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.archives import (
    ArchiveTooLarge,
    ArchiveUpload,
    archive_label,
    extract_archive,
    receive_archive,
)
from app.ingestion import IngestionError
from app.main import app, settings
from app.settings import Settings


def build_zip(entries: dict[str, bytes | str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in entries.items():
            info = zipfile.ZipInfo(name)
            # ZipInfo normalizes separators on Windows; keep the exact hostile name.
            info.filename = name
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data)
    return buffer.getvalue()


def workspace_limits(tmp_path, **values) -> Settings:
    # JobStore(workspace_limits(...)) must never load or evict personal reports.
    return Settings(workspace_root=str(tmp_path / "workspaces"), report_root=None, **values)


def leftovers(tmp_path) -> list[str]:
    return sorted(path.name for path in (tmp_path / "workspaces").glob("*"))


def extract(tmp_path, data: bytes, limits: Settings) -> list[str]:
    path = tmp_path / "upload.zip"
    path.write_bytes(data)
    with extract_archive(ArchiveUpload(name="project.zip", path=path), limits) as root:
        return sorted(item.relative_to(root).as_posix()
                      for item in root.rglob("*") if item.is_file())


def test_wrapper_folder_is_unwrapped_and_unindexed_paths_are_never_written(tmp_path):
    data = build_zip({
        "demo-main/": "",
        "demo-main/src/app.py": "x = 1",
        "demo-main/README.md": "# Demo",
        "demo-main/node_modules/left-pad/index.js": "module.exports = 1",
        "demo-main/.git/HEAD": "ref: ../../../../outside",
        "demo-main/.env": "TOKEN=hunter2",
        "demo-main/config/secrets/prod.json": "{}",
        "__MACOSX/demo-main/._app.py": b"\0\1",
    })
    assert extract(tmp_path, data, workspace_limits(tmp_path)) == ["README.md", "src/app.py"]
    assert leftovers(tmp_path) == []


def test_archives_without_a_single_wrapper_keep_their_layout(tmp_path):
    limits = workspace_limits(tmp_path)
    assert extract(tmp_path, build_zip({"main.py": "x = 1"}), limits) == ["main.py"]
    assert extract(tmp_path, build_zip({"api/app.py": "", "web/index.ts": ""}), limits) == [
        "api/app.py", "web/index.ts"]


@pytest.mark.parametrize("name", [
    "../evil.py", "src/../../evil.py", "/evil.py", "C:/evil.py", "src\\..\\..\\evil.py",
    "src/evil.py:stream", "src/con.py", "src/evil.py.", "src//evil.py", "src/\x01evil.py",
])
def test_unsafe_member_names_are_rejected_before_anything_is_written(tmp_path, name):
    data = build_zip({"src/app.py": "x = 1", name: "owned"})
    with pytest.raises(IngestionError, match="unsafe path"):
        extract(tmp_path, data, workspace_limits(tmp_path))
    assert not any(path.name.startswith("evil") for path in tmp_path.rglob("*"))
    assert leftovers(tmp_path) == []


def test_links_and_encrypted_members_are_rejected(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        link = zipfile.ZipInfo("src/link")
        link.external_attr = 0o120777 << 16
        bundle.writestr(link, "../../outside")
        bundle.writestr("src/app.py", "x = 1")
    with pytest.raises(IngestionError, match="links"):
        extract(tmp_path, buffer.getvalue(), workspace_limits(tmp_path))

    encrypted = bytearray(build_zip({"app.py": "x = 1"}))
    encrypted[encrypted.find(b"PK\x01\x02") + 8] |= 0x1
    with pytest.raises(IngestionError, match="Encrypted"):
        extract(tmp_path, bytes(encrypted), workspace_limits(tmp_path))
    assert leftovers(tmp_path) == []


def test_size_count_depth_and_conflict_limits(tmp_path):
    # Compresses to a few KB but declares more than the extraction budget.
    bomb = build_zip({"big.txt": b"\0" * (1024 * 1024 + 1), "small.py": ""})
    with pytest.raises(IngestionError, match="size limit"):
        extract(tmp_path, bomb, workspace_limits(tmp_path, max_repository_mb=1))
    with pytest.raises(IngestionError, match="file count"):
        extract(tmp_path, build_zip({"a.py": "", "b.py": "", "c.py": ""}),
                workspace_limits(tmp_path, max_file_count=2))
    with pytest.raises(IngestionError, match="path depth"):
        extract(tmp_path, build_zip({"a/b/c.py": "", "z.py": ""}),
                workspace_limits(tmp_path, max_path_depth=2))
    for entries in ({"src/App.py": "", "src/app.py": ""}, {"src": "", "src/app.py": ""}):
        with pytest.raises(IngestionError, match="conflicting"):
            extract(tmp_path, build_zip(entries), workspace_limits(tmp_path))
    with pytest.raises(IngestionError, match="no files"):
        extract(tmp_path, build_zip({"node_modules/x.js": "", ".env": "TOKEN=x"}),
                workspace_limits(tmp_path))
    assert leftovers(tmp_path) == []


def test_damaged_archive_is_reported_without_internal_detail(tmp_path):
    data = bytearray(build_zip({"app.py": "x = 1\n" * 1000}))
    start = data.find(b"PK\x03\x04") + 40
    data[start:start + 16] = b"\xff" * 16
    with pytest.raises(IngestionError, match="damaged"):
        extract(tmp_path, bytes(data), workspace_limits(tmp_path))
    assert leftovers(tmp_path) == []


@pytest.mark.parametrize(("value", "expected"), [
    ("project.zip", "project.zip"),
    ("C:\\fakepath\\My App (1).ZIP", "My App (1).zip"),
    ("../../evil.zip", "evil.zip"),
    ("José's <app>.zip", "Jos__s _app_.zip"),
    (" ..zip", "archive.zip"),
])
def test_archive_label_is_a_sanitized_display_name(value, expected):
    assert archive_label(value) == expected


@pytest.mark.parametrize("value", ["notes.txt", "", None, "zip"])
def test_archive_label_requires_a_zip_name(value):
    with pytest.raises(IngestionError):
        archive_label(value)


def test_streamed_upload_limit_applies_without_content_length(tmp_path):
    async def chunks():
        for _ in range(3):
            yield b"\0" * (512 * 1024)

    with pytest.raises(ArchiveTooLarge):
        asyncio.run(receive_archive(chunks(), workspace_limits(tmp_path, max_upload_mb=1)))
    assert leftovers(tmp_path) == []


@pytest.fixture
def isolated_service(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "workspace_root", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "report_root", None)


def upload(client, data, filename="project.zip", content_type="application/zip"):
    return client.post("/api/analyses/archive", params={"filename": filename}, content=data,
                       headers={"Content-Type": content_type})


def wait_for_terminal(client, job_id):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        body = client.get(f"/api/analyses/{job_id}").json()
        if body["status"] in {"complete", "failed"}:
            return body
        time.sleep(0.05)
    pytest.fail("Job did not finish")


def test_uploaded_archive_is_analyzed_like_a_repository(isolated_service, tmp_path):
    data = build_zip({"demo-main/index.ts": "export function run() {}\n",
                      "demo-main/.env": "TOKEN=hunter2"})
    with TestClient(app) as client:
        response = upload(client, data, filename="C:\\fakepath\\demo-main.zip")
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert wait_for_terminal(client, job_id)["status"] == "complete"
        repository = client.get(f"/api/analyses/{job_id}/atlas").json()["repository"]
        assert repository["source"] == "archive"
        assert repository["name"] == "demo-main.zip"
        assert repository["ref"] == "upload"
        assert "url" not in repository and "commit" not in repository
        source = client.get(f"/api/analyses/{job_id}/source", params={"path": "index.ts"})
        assert source.status_code == 200
        assert "export function run" in source.json()["text"]
        assert client.get(f"/api/analyses/{job_id}/source",
                          params={"path": ".env"}).status_code == 404
        assert '"phase":"extracting"' in client.get(f"/api/analyses/{job_id}/events").text
        recent = client.get("/api/analyses").json()["reports"]
        assert recent[0]["repository"]["name"] == "demo-main.zip"
    # The upload and its extraction workspace are both disposable.
    assert leftovers(tmp_path) == []


def test_upload_rejections_leave_nothing_behind(isolated_service, tmp_path, monkeypatch):
    zipped = build_zip({"app.py": "x = 1"})
    with TestClient(app) as client:
        assert upload(client, zipped, content_type="text/plain").status_code == 415
        misnamed = upload(client, zipped, filename="notes.txt")
        assert misnamed.status_code == 422
        assert isinstance(misnamed.json()["detail"], str)
        assert upload(client, b"not a zip").status_code == 422
        assert upload(client, b"").status_code == 422
        monkeypatch.setattr(settings, "max_upload_mb", 1)
        assert upload(client, b"\0" * (1024 * 1024 + 1)).status_code == 413
        monkeypatch.setattr(app.state.jobs, "busy", lambda: True)
        busy = upload(client, zipped)
        assert busy.status_code == 429
        assert busy.headers["Retry-After"] == "5"
        # Uploads are never described in JSON, so a client cannot name a server-side file.
        assert client.post("/api/analyses", json={"source": {
            "kind": "archive", "name": "x.zip", "path": str(tmp_path / "x.zip")}}).status_code == 422
    assert leftovers(tmp_path) == []


def test_zip_directory_budget_runs_before_zipinfo_allocation(tmp_path, monkeypatch):
    from app.archives import check_archive_directory
    path = tmp_path / "metadata.zip"
    path.write_bytes(build_zip({"a": "", "b": "", "c": ""}))
    monkeypatch.setattr("app.archives.MAX_DIRECTORY_ENTRIES", 2)
    with pytest.raises(IngestionError, match="metadata"):
        check_archive_directory(path)


def test_forged_directory_count_is_rejected(tmp_path):
    import struct

    from app.archives import check_archive_directory
    data = bytearray(build_zip({"a": "", "b": ""}))
    offset = data.rfind(b"PK\x05\x06")
    struct.pack_into("<HH", data, offset + 8, 1, 1)
    path = tmp_path / "forged.zip"
    path.write_bytes(data)
    with pytest.raises(IngestionError, match="count"):
        check_archive_directory(path)


def test_cancelled_queued_archive_removes_upload(tmp_path):
    from concurrent.futures import Future

    from app.jobs import JobStore
    store = JobStore(workspace_limits(tmp_path))
    store.executor.shutdown()
    future = Future()
    store.executor.submit = lambda *args: future
    upload_path = tmp_path / "queued.zip"
    upload_path.write_bytes(build_zip({"a.py": "x=1"}))
    store.create(ArchiveUpload("queued.zip", upload_path))
    assert upload_path.exists()
    future.cancel()
    assert not upload_path.exists()
    store.close()
