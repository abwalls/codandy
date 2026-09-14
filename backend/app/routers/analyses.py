import asyncio
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.archives import (
    ARCHIVE_CONTENT_TYPES,
    ArchiveTooLarge,
    ArchiveUpload,
    archive_label,
    receive_archive,
)
from app.dependency_checks import check_dependency, slots
from app.ingestion import IngestionError
from app.jobs import JobStore
from app.models import AnalysisCreate, AnalysisJob, AtlasDocument, SourceFile

router = APIRouter(prefix="/analyses", tags=["analyses"])


def store(request: Request) -> JobStore:
    jobs = getattr(request.app.state, "jobs", None)
    if jobs is None:
        raise HTTPException(503, "Analysis service is starting")
    return jobs


@router.post("", response_model=AnalysisJob, status_code=202)
async def create_analysis(body: AnalysisCreate, request: Request) -> AnalysisJob:
    try:
        return store(request).create(body)
    except IngestionError as exc:
        raise HTTPException(429, str(exc), headers={"Retry-After": "5"}) from exc


@router.post("/archive", response_model=AnalysisJob, status_code=202)
async def create_archive_analysis(request: Request) -> AnalysisJob:
    """Accept a raw .zip body. Errors are plain strings so the client can show them."""
    jobs = store(request)
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in ARCHIVE_CONTENT_TYPES:
        raise HTTPException(415, "Upload the project as a .zip archive")
    try:
        name = archive_label(request.query_params.get("filename"))
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > jobs.limits.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"ZIP uploads are limited to {jobs.limits.max_upload_mb} MB")
    # Checked before streaming so a busy backend does not receive the whole body first;
    # create() re-checks atomically.
    if jobs.busy():
        raise HTTPException(429, "An analysis is already running; retry after it finishes",
                            headers={"Retry-After": "5"})
    try:
        path = await receive_archive(request.stream(), jobs.limits)
    except ArchiveTooLarge as exc:
        raise HTTPException(413, str(exc)) from exc
    except IngestionError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        return jobs.create(ArchiveUpload(name=name, path=path))
    except IngestionError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(429, str(exc), headers={"Retry-After": "5"}) from exc


@router.get("")
async def recent_analyses(request: Request):
    jobs = store(request)
    return {"reports": jobs.recent(), "persistent": jobs.storage is not None}


@router.get("/{analysis_id}", response_model=AnalysisJob)
async def get_analysis(analysis_id: UUID, request: Request) -> AnalysisJob:
    job = store(request).get(analysis_id)
    if job is None:
        raise HTTPException(404, "Analysis not found or expired")
    return job


@router.get("/{analysis_id}/atlas", response_model=AtlasDocument)
async def get_atlas(analysis_id: UUID, request: Request) -> AtlasDocument:
    job = await get_analysis(analysis_id, request)
    atlas = store(request).result(analysis_id)
    if atlas is None:
        raise HTTPException(409, job.error or "Atlas is not ready")
    return atlas


@router.delete("/{analysis_id}")
async def remove_analysis(analysis_id: UUID, request: Request):
    try:
        removed = store(request).remove(analysis_id)
    except IngestionError as exc:
        raise HTTPException(409, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(503, "Report storage is unavailable; removal was not completed") from exc
    if not removed:
        raise HTTPException(404, "Analysis not found or expired")
    return {"deleted": str(analysis_id)}


@router.post("/{analysis_id}/dependencies")
def dependency_check(analysis_id: UUID, request: Request,
                     node_id: str = Query(min_length=1, max_length=200)):
    jobs = store(request)
    if jobs.get(analysis_id) is None:
        raise HTTPException(404, "Analysis not found or expired")
    atlas = jobs.result(analysis_id)
    if atlas is None:
        raise HTTPException(409, "Atlas is not ready")
    node = next((node for node in atlas.nodes if node.id == node_id and node.kind == "dependency"), None)
    if node is None:
        raise HTTPException(404, "Dependency not found in this atlas")
    if not slots.acquire(blocking=False):
        raise HTTPException(429, "Dependency checks are busy; retry shortly")
    try:
        return check_dependency(node)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        slots.release()


@router.get("/{analysis_id}/source", response_model=SourceFile)
async def get_source(analysis_id: UUID, request: Request,
                     path: str = Query(min_length=1, max_length=1024)) -> SourceFile:
    job = await get_analysis(analysis_id, request)
    if store(request).result(analysis_id) is None:
        raise HTTPException(409, job.error or "Atlas is not ready")
    source = store(request).source(analysis_id, path)
    if source is None:
        raise HTTPException(404, "Source text was not captured for this path")
    return source


@router.get("/{analysis_id}/events")
async def events(analysis_id: UUID, request: Request,
                 last_event_id: int = Header(default=0, ge=0)):
    await get_analysis(analysis_id, request)
    jobs = store(request)

    async def stream():
        cursor = last_event_id
        heartbeat = 0
        while not await request.is_disconnected():
            batch, terminal = jobs.read_events(analysis_id, cursor)
            for payload in batch:
                cursor += 1
                yield f"id: {cursor}\nevent: progress\ndata: {payload}\n\n"
            if terminal:
                return
            heartbeat += 1
            if heartbeat % 40 == 0:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
