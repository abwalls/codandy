"""Local-only telemetry import and explicitly requested Sentry event retrieval."""

import threading

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.debugging.models import DebuggingLimits, Observation
from app.debugging.payload import NormalizationError
from app.debugging.sentry_client import SentryError, fetch_event
from app.debugging.sentry_event import normalize_sentry_event_bytes
from app.debugging.stacks import normalize_stack_text
from app.settings import settings

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
busy = threading.Lock()


def local_only(request: Request):
    if (not request.client or request.client.host not in LOCAL_HOSTS
            or request.url.hostname not in LOCAL_HOSTS
            or request.headers.get("x-codandy-local") != "1"):
        raise HTTPException(403, "Debugging imports are available on this computer only")
    origin = request.headers.get("origin")
    if origin and origin not in {f"http://{host}:{port}" for host in ("localhost", "127.0.0.1")
                                for port in (3000, 5173, 8000)}:
        raise HTTPException(403, "Unapproved browser origin")


router = APIRouter(prefix="/debugging", tags=["debugging"], dependencies=[Depends(local_only)])


@router.get("/sentry/status")
def status():
    return {"configured": bool(settings.sentry_token.get_secret_value() and settings.sentry_organization),
            "host": settings.sentry_host, "organization": settings.sentry_organization,
            "verified": False}


@router.post("/imports", response_model=Observation)
async def import_observation(request: Request):
    media = request.headers.get("content-type", "").split(";", 1)[0].strip()
    if media not in {"application/json", "text/plain"}:
        raise HTTPException(415, "Use a Sentry REST JSON event or a plain-text stack")
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "Another debugging request is running")
    try:
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > DebuggingLimits().max_payload_bytes:
                raise HTTPException(413, "Import exceeds the 2 MiB budget")
            data.extend(chunk)
        if media == "application/json":
            observation = await run_in_threadpool(normalize_sentry_event_bytes, bytes(data))
            return request.app.state.investigations.remember(observation)
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "Stack text must be UTF-8") from None
        observation = await run_in_threadpool(normalize_stack_text, text)
        return request.app.state.investigations.remember(observation)
    except NormalizationError as exc:
        raise HTTPException(422, str(exc)) from None
    finally:
        busy.release()


@router.post("/sentry/issues/{issue}/events/{event}", response_model=Observation)
def retrieve(issue: str, event: str, request: Request):
    if not busy.acquire(blocking=False):
        raise HTTPException(409, "Another debugging request is running")
    try:
        return request.app.state.investigations.remember(fetch_event(settings, issue, event))
    except SentryError as exc:
        raise HTTPException(502, str(exc)) from None
    finally:
        busy.release()
