"""Bounded, static-only ingestion. Never invoke repository-provided tooling."""

import ipaddress
import os
import re
import signal
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from app.settings import Settings


class IngestionError(ValueError):
    pass


def validate_git_url(value: str) -> str:
    """M1 deliberately accepts only canonical public HTTPS GitHub repositories."""
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+/?", parsed.path)
    ):
        raise IngestionError("Use an HTTPS github.com/owner/repository URL without credentials")
    path = parsed.path.rstrip("/")
    name = path.rsplit("/", 1)[1].removesuffix(".git")
    if name in {"", ".", ".."}:
        raise IngestionError("Invalid repository name")
    return f"https://github.com/{path.split('/')[1]}/{name}.git"


def validate_ref(value: str | None) -> str | None:
    if value is not None and (
        len(value) > 200
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_./-]*", value)
        or ".." in value
        or "//" in value
        or value.endswith(("/", ".", ".lock"))
    ):
        raise IngestionError("Invalid branch or tag")
    return value


def public_github_address() -> str:
    addresses = {item[4][0] for item in socket.getaddrinfo("github.com", 443)}
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise IngestionError("GitHub must resolve only to public addresses")
    # Pin DNS for the actual HTTPS connection, closing the DNS rebinding gap.
    return min(addresses, key=lambda address: (":" in address, address))


def check_workspace(root: Path, limits: Settings) -> None:
    total = count = 0
    for directory, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(directory) / name
            if path.is_symlink() or path.is_junction():
                raise IngestionError("Repository links are not supported")
            if len(path.relative_to(root).parts) > limits.max_path_depth:
                raise IngestionError("Repository exceeds path depth limit")
        for name in files:
            try:
                size = (Path(directory) / name).stat().st_size
            except OSError:
                # This runs repeatedly while Git is still writing, and Git creates and
                # removes lock and temporary files as it works. A path that disappears
                # between the walk and the stat cannot count toward the size limit.
                continue
            count += 1
            total += size
            if count > limits.max_file_count or total > limits.max_repository_mb * 1024 * 1024:
                raise IngestionError("Repository exceeds file count or size limit")


def check_tree(data: bytes, limits: Settings) -> None:
    total = count = 0
    for entry in data.split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, _, size = metadata.split()
        if mode not in {b"100644", b"100755"} or kind != b"blob":
            raise IngestionError("Symlinks and submodules are not supported")
        parts = path.replace(b"\\", b"/").split(b"/")
        if any(part in {b"", b".", b".."} or b":" in part for part in parts):
            raise IngestionError("Unsafe repository path")
        if len(parts) > limits.max_path_depth:
            raise IngestionError("Repository exceeds path depth limit")
        count += 1
        total += int(size)
        if count > limits.max_file_count or total > limits.max_repository_mb * 1024 * 1024:
            raise IngestionError("Repository exceeds file count or size limit")


def _run(args: list[str], root: Path, env: dict[str, str], deadline: float,
         limits: Settings) -> bytes:
    # Files avoid pipe deadlocks; both output and clone storage count toward the disk limit.
    with (tempfile.TemporaryFile(dir=root) as output,
          subprocess.Popen(args, cwd=root, env=env, stdin=subprocess.DEVNULL,
                          stdout=output, stderr=subprocess.DEVNULL,
                          start_new_session=os.name != "nt") as process):
        try:
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise IngestionError("Repository ingestion timed out")
                check_workspace(root, limits)
                time.sleep(0.05)
            check_workspace(root, limits)
            if process.returncode:
                raise IngestionError("Git operation failed; check public access and branch/tag")
            if output.tell() > limits.max_repository_mb * 1024 * 1024:
                raise IngestionError("Git output exceeds size limit")
            output.seek(0)
            return output.read()
        finally:
            if process.poll() is None:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   check=False)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                if process.poll() is None:
                    process.kill()
            process.wait()


@contextmanager
def clone_repository(url: str, ref: str | None, limits: Settings):
    url, ref = validate_git_url(url), validate_ref(ref)
    address = public_github_address()
    if ":" in address:
        address = f"[{address}]"
    workspace = Path(limits.workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="atlas-", dir=workspace) as temporary:
        root = Path(temporary)
        empty = root / "empty"
        empty.mkdir()
        # Do not inherit Git configuration, tokens, proxies, SSH, or credential helpers.
        env = {key: value for key, value in os.environ.items()
               if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}}
        env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(empty / "config"),
                    "GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1",
                    "GIT_ALLOW_PROTOCOL": "https", "HOME": str(empty),
                    "USERPROFILE": str(empty)})
        git = ["git", "-c", "credential.helper=", "-c", "http.followRedirects=false",
               "-c", "http.proxy=", "-c", "http.sslVerify=true",
               "-c", f"http.curloptResolve=github.com:443:{address}",
               "-c", f"core.hooksPath={empty.as_posix()}",
               "-c", "core.protectNTFS=true", "-c", "core.protectHFS=true"]
        deadline = time.monotonic() + limits.clone_timeout_seconds
        clone = ["clone", "--depth=1", "--single-branch", "--no-tags", "--no-checkout",
                 f"--template={empty.as_posix()}"]
        if ref:
            clone += ["--branch", ref]
        _run(git + clone + ["--", url, "repository"], root, env, deadline, limits)
        repository_git = git + ["-C", str(root / "repository")]
        tree = _run(repository_git + ["ls-tree", "-rlz", "HEAD"], root, env, deadline, limits)
        check_tree(tree, limits)
        _run(repository_git + ["checkout", "--force", "HEAD", "--", "."],
             root, env, deadline, limits)
        yield root / "repository"
