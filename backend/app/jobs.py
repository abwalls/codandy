"""Bounded single-worker service with optional local completed-report persistence."""

import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

from app.ingestion import IngestionError, clone_repository
from app.models import AnalysisCreate, AnalysisJob, AtlasDocument, SourceFile
from app.report_storage import ReportStorage, Snapshot
from app.settings import Settings
from app.sources import collect_sources
from app.worker import analyze_isolated as analyze_repository


class JobStore:
    def __init__(self, limits: Settings):
        self.limits = limits
        self.lock = threading.RLock()
        self.jobs: dict[UUID, AnalysisJob] = {}
        self.events: dict[UUID, list[str]] = {}
        self.results: dict[UUID, AtlasDocument] = {}
        self.sources: dict[UUID, dict[str, SourceFile]] = {}
        self.storage = ReportStorage(limits.report_root) if limits.report_root else None
        if self.storage:
            for snapshot in self.storage.load(limits.max_jobs):
                job_id = snapshot.job.id
                self.jobs[job_id] = snapshot.job
                self.events[job_id] = snapshot.events
                self.results[job_id] = snapshot.atlas
                self.sources[job_id] = snapshot.sources
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="atlas")

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)

    def create(self, request: AnalysisCreate) -> AnalysisJob:
        with self.lock:
            if any(job.status in {"queued", "analyzing"} for job in self.jobs.values()):
                raise IngestionError("An analysis is already running; retry after it finishes")
            while len(self.jobs) >= self.limits.max_jobs:
                oldest = next(iter(self.jobs))
                if self.storage:
                    self.storage.remove(oldest)
                del self.jobs[oldest], self.events[oldest]
                self.results.pop(oldest, None)
                self.sources.pop(oldest, None)
            job = AnalysisJob()
            self.jobs[job.id] = job
            self.events[job.id] = [job.model_dump_json()]
            snapshot = job.model_copy(deep=True)
            self.executor.submit(self.run, job.id, request)
            return snapshot

    def get(self, job_id: UUID) -> AnalysisJob | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def update(self, job_id: UUID, phase: str, progress: int, status="analyzing", error=None):
        with self.lock:
            job = self.jobs[job_id]
            job.phase, job.progress, job.status, job.error = phase, progress, status, error
            self.events[job_id].append(job.model_dump_json())

    def run(self, job_id: UUID, request: AnalysisCreate):
        try:
            self.update(job_id, "cloning", 5)
            with clone_repository(request.source.url, request.source.ref, self.limits) as root:
                self.update(job_id, "detecting", 30)
                atlas = analyze_repository(root, request.source.url, request.source.ref, self.limits,
                                           lambda phase, value: self.update(job_id, phase, value))
                git_head = (root / ".git" / "HEAD").read_text().strip()
                if git_head.startswith("ref: "):
                    head_ref = git_head.removeprefix("ref: ")
                    ref_file = root / ".git" / head_ref
                    git_head = ref_file.read_text().strip() if ref_file.is_file() else ""
                    atlas.repository["branch"] = head_ref.removeprefix("refs/heads/")
                if len(git_head) in {40, 64} and all(c in "0123456789abcdef" for c in git_head):
                    atlas.repository["commit"] = git_head
                # Captured before the workspace is destroyed; the atlas itself
                # stays a graph artifact and never carries source bodies.
                sources, omitted = collect_sources(root, atlas, self.limits)
                if omitted:
                    atlas.limitations.append(
                        f"Source text is unavailable for {omitted} indexed files; the viewer "
                        "budget, binary content or excluded paths took precedence.")
                self.update(job_id, "validating", 90)
                artifact = root / ".codeatlas"
                artifact.mkdir(exist_ok=True)
                payload = atlas.model_dump_json(indent=2)
                (artifact / "atlas.json").write_text(payload, encoding="utf-8")
                validated = AtlasDocument.model_validate_json(payload)
            with self.lock:
                if self.storage:
                    completed = self.jobs[job_id].model_copy(update={
                        "phase": "complete", "progress": 100, "status": "complete"})
                    try:
                        self.storage.save(Snapshot(job=completed, atlas=validated, sources=sources,
                            events=[*self.events[job_id], completed.model_dump_json()]))
                    except OSError as exc:
                        raise IngestionError(
                            "Could not save the completed report. Check local report storage "
                            "permissions, free space, and the 128 MB snapshot limit.") from exc
                self.results[job_id] = validated
                self.sources[job_id] = sources
                self.update(job_id, "complete", 100, status="complete")
        except IngestionError as exc:
            self.update(job_id, "failed", 0, status="failed", error=str(exc))
        except Exception:  # noqa: BLE001 - contain worker failures and sanitize public errors
            self.update(job_id, "failed", 0, status="failed",
                        error="Analysis failed. Check Git availability and local workspace access.")

    def read_events(self, job_id: UUID, cursor: int) -> tuple[list[str], bool]:
        with self.lock:
            if job_id not in self.jobs:
                return [], True
            return (self.events[job_id][cursor:],
                    self.jobs[job_id].status in {"complete", "failed"})

    def result(self, job_id: UUID) -> AtlasDocument | None:
        with self.lock:
            return self.results.get(job_id)

    def recent(self) -> list[dict]:
        with self.lock:
            return [{"id": str(job_id), "repository": atlas.repository,
                     "created_at": self.jobs[job_id].created_at.isoformat()}
                    for job_id, atlas in reversed(list(self.results.items()))]

    def remove(self, job_id: UUID) -> bool:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                return False
            if job.status in {"queued", "analyzing"}:
                raise IngestionError("A running analysis cannot be removed")
            if self.storage:
                self.storage.remove(job_id)
            self.jobs.pop(job_id, None)
            self.events.pop(job_id, None)
            self.results.pop(job_id, None)
            self.sources.pop(job_id, None)
            return True

    def source(self, job_id: UUID, path: str) -> SourceFile | None:
        """Only paths captured during analysis are addressable; no disk access here."""
        with self.lock:
            return self.sources.get(job_id, {}).get(path)
