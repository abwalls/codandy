import sys
import time

import pytest
from fastapi.testclient import TestClient

from app import ingestion
from app.main import app
from app.models import RepositorySource
from app.settings import Settings


@pytest.mark.parametrize("url", [
    "http://github.com/a/b", "https://user:secret@github.com/a/b",
    "https://localhost/a/b", "https://127.0.0.1/a/b", "file:///tmp/repo",
    "https://github.com.evil.test/a/b", "https://github.com/a/b?token=secret",
    "https://github.com/a/b#main", "https://github.com:443/a/b",
    "https://github.com/a/..", "https://github.com/a/b/tree/main",
    "https://github.com/a/%2e%2e", "git@github.com:a/b",
])
def test_reject_unsafe_urls(url):
    with pytest.raises(ValueError):
        RepositorySource(url=url)


def test_normalize_url():
    assert RepositorySource(url="https://github.com/org/repo/").url == (
        "https://github.com/org/repo.git"
    )


@pytest.mark.parametrize("ref", ["-main", "main~1", "../main", "a//b", "a.lock", "a\n"])
def test_reject_unsafe_refs(ref):
    with pytest.raises(ValueError):
        RepositorySource(url="https://github.com/org/repo", ref=ref)


def tree(path=b"src/index.ts", mode=b"100644", size=b"100"):
    return mode + b" blob " + b"a" * 40 + b" " + size + b"\t" + path + b"\0"


def test_tree_limits_and_links():
    limits = Settings(max_file_count=1, max_path_depth=2, max_repository_mb=1)
    ingestion.check_tree(tree(), limits)
    for data in [tree() * 2, tree(b"a/b/c.ts"), tree(size=b"1048577"),
                 tree(mode=b"120000"), tree(mode=b"160000"), tree(b"../secret"),
                 tree(b"C:/secret"), tree(b"a\\..\\secret")]:
        with pytest.raises(ingestion.IngestionError):
            ingestion.check_tree(data, limits)


def test_workspace_limits(tmp_path):
    (tmp_path / "first").touch()
    (tmp_path / "second").touch()
    with pytest.raises(ingestion.IngestionError, match="file count"):
        ingestion.check_workspace(tmp_path, Settings(max_file_count=1))


def test_workspace_tolerates_files_removed_mid_walk(tmp_path, monkeypatch):
    # check_workspace runs repeatedly while Git is still writing, so lock and
    # temporary files routinely vanish between the walk and the stat.
    (tmp_path / "kept").write_bytes(b"x" * 10)
    (tmp_path / "also-kept").write_bytes(b"x" * 10)
    real_walk = ingestion.os.walk

    def walk(root, **kwargs):
        for directory, directories, files in real_walk(root, **kwargs):
            yield directory, directories, [*files, "HEAD.lock"]

    monkeypatch.setattr(ingestion.os, "walk", walk)
    ingestion.check_workspace(tmp_path, Settings())
    # Surviving files are still measured, so real limits keep applying.
    with pytest.raises(ingestion.IngestionError, match="file count"):
        ingestion.check_workspace(tmp_path, Settings(max_file_count=1))


def test_private_dns_rejected(monkeypatch):
    monkeypatch.setattr(ingestion.socket, "getaddrinfo", lambda *_: [
        (None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(ingestion.IngestionError, match="public addresses"):
        ingestion.public_github_address()


@pytest.mark.parametrize("fail", [False, True])
def test_clone_safety_and_cleanup(tmp_path, monkeypatch, fail):
    monkeypatch.setattr(ingestion, "public_github_address", lambda: "140.82.112.3")
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GITHUB_TOKEN", "must-not-inherit")
    calls = []

    def run(args, root, env, deadline, limits):
        calls.append(args)
        assert "GITHUB_TOKEN" not in env and "GIT_CONFIG_COUNT" not in env
        assert "http.followRedirects=false" in args
        assert "http.curloptResolve=github.com:443:140.82.112.3" in args
        if "clone" in args:
            (root / "repository").mkdir()
        if "ls-tree" in args:
            return tree(mode=b"120000") if fail else tree()
        return b""

    monkeypatch.setattr(ingestion, "_run", run)
    limits = Settings(workspace_root=str(tmp_path))
    if fail:
        with (pytest.raises(ingestion.IngestionError),
              ingestion.clone_repository("https://github.com/org/repo", None, limits)):
            pytest.fail("Unsafe tree reached checkout")
        assert not any("checkout" in args for args in calls)
    else:
        with ingestion.clone_repository("https://github.com/org/repo", "main", limits) as repo:
            assert repo.is_dir()
        assert any("checkout" in args for args in calls)
    assert list(tmp_path.iterdir()) == []


def test_process_timeout(tmp_path):
    with pytest.raises(ingestion.IngestionError, match="timed out"):
        ingestion._run([sys.executable, "-c", "import time; time.sleep(30)"],
                       tmp_path, dict(ingestion.os.environ), time.monotonic() + 0.1,
                       Settings())


def test_git_failure_is_sanitized(tmp_path):
    with pytest.raises(ingestion.IngestionError, match="Git operation failed"):
        ingestion._run([sys.executable, "-c", "raise SystemExit('secret')"],
                       tmp_path, dict(ingestion.os.environ), time.monotonic() + 10,
                       Settings())


def test_api_rejects_unsafe_input():
    with TestClient(app) as client:
        assert client.post("/api/analyses", json={"source": {
            "url": "https://localhost/a/b"}}).status_code == 422
        assert client.get("/api/analyses/00000000-0000-0000-0000-000000000000").status_code == 404
