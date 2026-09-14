"""Opt-in local snapshots. One API process owns this directory; no shared-worker claims."""

import os
import tempfile
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field, ValidationError

from app.models import AnalysisJob, AtlasDocument, SourceFile

MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024


class Snapshot(BaseModel):
    version: int = Field(default=1, ge=1, le=1)
    job: AnalysisJob
    atlas: AtlasDocument
    sources: dict[str, SourceFile]
    events: list[str]


class ReportStorage:
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, snapshot: Snapshot):
        payload = snapshot.model_dump_json().encode("utf-8")
        if len(payload) > MAX_SNAPSHOT_BYTES:
            raise OSError("Snapshot exceeds local storage limit")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root / f"{snapshot.job.id}.json")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def remove(self, job_id: UUID):
        (self.root / f"{job_id}.json").unlink(missing_ok=True)

    def load(self, limit: int) -> list[Snapshot]:
        restored = []
        # Only application-named UUID files are candidates; never follow symlinks.
        candidates = []
        for path in self.root.glob("*.json"):
            try:
                UUID(path.stem)
                if not path.is_symlink() and path.stat().st_size <= MAX_SNAPSHOT_BYTES:
                    candidates.append(path)
            except (ValueError, OSError):
                continue
        for path in sorted(candidates, key=lambda entry: entry.stat().st_mtime, reverse=True):
            try:
                snapshot = Snapshot.model_validate_json(path.read_bytes())
                if str(snapshot.job.id) != path.stem or snapshot.job.status != "complete":
                    continue
                file_paths = {node.path for node in snapshot.atlas.nodes if node.kind == "file"}
                if any(key != source.path or key not in file_paths
                       for key, source in snapshot.sources.items()):
                    continue
                snapshots = [AnalysisJob.model_validate_json(event) for event in snapshot.events]
                if not snapshots or any(job.id != snapshot.job.id for job in snapshots):
                    continue
                if snapshots[-1] != snapshot.job:
                    continue
                if len(restored) < limit:
                    restored.append(snapshot)
                else:
                    self.remove(snapshot.job.id)
            except (OSError, ValueError, ValidationError):
                continue
        return list(reversed(restored))
