"""Bounded, static-only ZIP intake. Archive content is extracted, never executed.

An uploaded archive is as untrusted as a cloned repository. Member names are validated
before anything is written, declared and actual sizes are both limited, links and
encrypted members are rejected, and paths the analyzer would never index (excluded
directories and secret-named files) are not written to disk at all.
"""

import asyncio
import re
import struct
import tempfile
import time
import zipfile
import zlib
from collections.abc import AsyncIterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.analyzer import EXCLUDED_DIRS, SECRET_NAME
from app.ingestion import IngestionError, check_workspace
from app.settings import Settings

# Neither type is a CORS "simple" content type, so a cross-site page cannot post an
# archive to a local backend without a preflight the CORS allowlist rejects.
ARCHIVE_CONTENT_TYPES = {"application/zip", "application/x-zip-compressed"}
UNSAFE_CHARACTERS = re.compile(r'[\x00-\x1f<>:"|?*]')
RESERVED_NAME = re.compile(r"(?i)^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$")
LINK_MODE = 0o120000
CHUNK_BYTES = 1024 * 1024
MAX_DIRECTORY_BYTES = 8 * 1024 * 1024
MAX_DIRECTORY_ENTRIES = 50000


class ArchiveTooLarge(IngestionError):
    pass


@dataclass(frozen=True)
class ArchiveUpload:
    """Server-side handle for an upload the router just wrote.

    Deliberately not part of the JSON request models: a client must never be able to name
    a server path for the worker to extract or delete.
    """

    name: str
    path: Path


def archive_label(value: str | None) -> str:
    """Display name for the report. It never becomes a filesystem path."""
    name = PurePosixPath((value or "").replace("\\", "/")).name
    if not name.lower().endswith(".zip"):
        raise IngestionError("Upload the project as a .zip archive")
    stem = re.sub(r"[^A-Za-z0-9 _.()+-]", "_", name[:-4]).strip(" .")[:100]
    return f"{stem or 'archive'}.zip"


async def receive_archive(chunks: AsyncIterator[bytes], limits: Settings) -> Path:
    """Stream an upload into the workspace root, enforcing the limit on bytes received.

    Content-Length is checked earlier as a courtesy, but chunked uploads do not send it,
    so this count is the real limit.
    """
    workspace = Path(limits.workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    limit = limits.max_upload_mb * 1024 * 1024
    descriptor, name = tempfile.mkstemp(prefix="upload-", suffix=".zip", dir=workspace)
    path = Path(name)
    try:
        received = 0
        handle = await asyncio.to_thread(open, descriptor, "wb")
        with handle:
            async for chunk in chunks:
                received += len(chunk)
                if received > limit:
                    raise ArchiveTooLarge(f"ZIP uploads are limited to {limits.max_upload_mb} MB")
                await asyncio.to_thread(handle.write, chunk)
        if not received:
            raise IngestionError("The uploaded archive is empty")
        if not await asyncio.to_thread(zipfile.is_zipfile, path):
            raise IngestionError("The upload is not a valid .zip archive")
        return path
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _member_parts(name: str) -> tuple[str, ...]:
    normalized = name.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    parts = tuple(normalized.rstrip("/").split("/"))
    if normalized.startswith("/") or any(
            part in {"", ".", ".."} or UNSAFE_CHARACTERS.search(part)
            or part != part.rstrip(". ") or RESERVED_NAME.match(part) for part in parts):
        raise IngestionError("Archive contains an unsafe path")
    return parts


def _select_members(bundle: zipfile.ZipFile, limits: Settings):
    members = []
    for info in bundle.infolist():
        if info.flag_bits & 0x1:
            raise IngestionError("Encrypted archives are not supported")
        if (info.external_attr >> 16) & 0o170000 == LINK_MODE:
            raise IngestionError("Archive links are not supported")
        parts = _member_parts(info.filename)
        # macOS Finder adds resource-fork copies that are not part of the project.
        if parts[0] != "__MACOSX":
            members.append((info, parts))
    # "Download ZIP" and most archivers wrap everything in one folder (repo-main/...).
    # Unwrap it so report paths match the repository layout.
    if len({parts[0] for _, parts in members}) == 1 and all(
            len(parts) > 1 for info, parts in members if not info.is_dir()):
        members = [(info, parts[1:]) for info, parts in members if len(parts) > 1]

    max_bytes = limits.max_repository_mb * 1024 * 1024
    selected, files, directories, declared = [], set(), set(), 0
    for info, parts in members:
        folders = parts if info.is_dir() else parts[:-1]
        # Mirrors the analyzer's walk: these paths would never be indexed.
        if any(part.lower() in EXCLUDED_DIRS or SECRET_NAME.search(part) for part in folders):
            continue
        if info.is_dir() or SECRET_NAME.search(parts[-1]):
            continue
        if len(parts) > limits.max_path_depth:
            raise IngestionError("Archive exceeds path depth limit")
        # Case-folded so an archive cannot overwrite a file on case-insensitive disks.
        key = "/".join(parts).casefold()
        parents = {"/".join(parts[:index]).casefold() for index in range(1, len(parts))}
        if key in files or key in directories or parents & files:
            raise IngestionError("Archive contains duplicate or conflicting paths")
        files.add(key)
        directories |= parents
        declared += info.file_size
        selected.append((info, parts))
        if len(selected) > limits.max_file_count or declared > max_bytes:
            raise IngestionError("Archive exceeds file count or size limit")
    if not selected:
        raise IngestionError("The archive contains no files outside excluded folders")
    return selected


def check_archive_directory(archive: Path):
    """Bound metadata before ZipFile constructs ZipInfo objects (PKWARE APPNOTE 4.3.12/16)."""
    with archive.open("rb") as stream:
        size = stream.seek(0, 2)
        tail_size = min(size, 65535 + 22)
        stream.seek(size - tail_size)
        tail = stream.read(tail_size)
        offset = tail.rfind(b"PK\x05\x06")
        if offset < 0 or offset + 22 > len(tail):
            raise IngestionError("The archive has no valid directory record")
        _, disk, start_disk, on_disk, total, directory_size, directory_offset, comment_size = struct.unpack_from("<4s4H2IH", tail, offset)
        end_position = size - tail_size + offset
        if offset + 22 + comment_size != len(tail):
            raise IngestionError("The archive has invalid trailing directory data")
        if disk or start_disk or on_disk != total or total == 65535 or directory_size == 0xffffffff or directory_offset == 0xffffffff:
            raise IngestionError("Split and ZIP64 directory archives are not supported; upload a smaller ordinary ZIP")
        if total > MAX_DIRECTORY_ENTRIES or directory_size > MAX_DIRECTORY_BYTES:
            raise IngestionError("ZIP directory metadata exceeds the limit; omit dependencies and build output")
        if directory_size > end_position or directory_offset > end_position - directory_size:
            raise IngestionError("The archive directory location is invalid")
        # ZipFile supports a prefix before the ZIP; use the physical directory location.
        stream.seek(end_position - directory_size)
        directory = stream.read(directory_size)
        position = count = 0
        while position < len(directory):
            if position + 46 > len(directory) or directory[position:position + 4] != b"PK\x01\x02":
                raise IngestionError("The archive directory is malformed or unsupported")
            name, extra, comment = struct.unpack_from("<3H", directory, position + 28)
            position += 46 + name + extra + comment
            count += 1
            if count > MAX_DIRECTORY_ENTRIES or position > len(directory):
                raise IngestionError("The archive directory exceeds its metadata budget")
        if count != total:
            raise IngestionError("The archive directory entry count is inconsistent")


def _extract(archive: Path, root: Path, limits: Settings, deadline: float) -> None:
    max_bytes = limits.max_repository_mb * 1024 * 1024
    resolved_root = root.resolve()
    written = 0
    check_archive_directory(archive)
    with zipfile.ZipFile(archive) as bundle:
        for info, parts in _select_members(bundle, limits):
            target = root.joinpath(*parts)
            if not target.resolve().is_relative_to(resolved_root):
                raise IngestionError("Archive contains an unsafe path")
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open("xb") as output:
                # Declared sizes are attacker-controlled, so actual output is counted too.
                while chunk := source.read(CHUNK_BYTES):
                    written += len(chunk)
                    if written > max_bytes:
                        raise IngestionError("Archive exceeds file count or size limit")
                    if time.monotonic() >= deadline:
                        raise IngestionError("Archive extraction timed out")
                    output.write(chunk)


@contextmanager
def extract_archive(upload: ArchiveUpload, limits: Settings):
    workspace = Path(limits.workspace_root).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + limits.clone_timeout_seconds
    with tempfile.TemporaryDirectory(prefix="atlas-", dir=workspace) as temporary:
        root = Path(temporary) / "repository"
        root.mkdir()
        try:
            _extract(upload.path, root, limits, deadline)
        except (zipfile.BadZipFile, zipfile.LargeZipFile, NotImplementedError, RuntimeError,
                EOFError, zlib.error) as exc:
            raise IngestionError(
                "The archive is damaged or uses unsupported compression") from exc
        check_workspace(root, limits)
        yield root
