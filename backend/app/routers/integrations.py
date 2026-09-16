import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.debugging.models import DebuggingLimits
from app.debugging.payload import load_json
from app.integrations import linear
from app.integrations.tickets import Draft, Submission, TicketConflict, review
from app.routers.debugging import local_only
from app.settings import settings

router = APIRouter(prefix="/integrations", tags=["integrations"], dependencies=[Depends(local_only)])


def operation(fn, *args):
    try:
        return fn(*args)
    except TicketConflict as exc:
        raise HTTPException(409, str(exc)) from None
    except linear.ProviderError as exc:
        raise HTTPException(502, str(exc)) from None
    except (OSError, sqlite3.Error):
        raise HTTPException(503, "Local ticket ledger is unavailable; check Linear before retrying a submission") from None
    except ValueError:
        raise HTTPException(422, "Invalid ticket draft") from None


@router.get("")
def status():
    return {"provider": "linear", "configured": bool(settings.linear_api_key.get_secret_value()),
            "persistent": bool(settings.integration_root),
            "settings_hint": "Set CODANDY_LINEAR_API_KEY in backend/.env and restart the backend. "
                             "Use a personal key restricted to the intended teams with issue-creation permission."}


@router.post("/linear/test")
def test_connection():
    operation(linear.test_connection, settings)
    return {"verified": True}


@router.get("/linear/teams")
def teams():
    return operation(linear.teams, settings)


async def body(request, schema):
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
        raise HTTPException(415, "Use application/json")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > 100000:
            raise HTTPException(413, "Ticket request exceeds 100 KB")
        data.extend(chunk)
    try:
        return schema.model_validate(load_json(bytes(data), DebuggingLimits(max_payload_bytes=100000)))
    except ValueError:
        raise HTTPException(422, "Invalid ticket request") from None


@router.post("/tickets/review")
async def prepare(request: Request):
    return operation(review, settings, await body(request, Draft))


@router.post("/tickets")
async def create(request: Request):
    draft = await body(request, Submission)
    return await run_in_threadpool(operation, request.app.state.tickets.submit, settings, draft)


@router.get("/tickets")
def history(request: Request):
    return operation(request.app.state.tickets.history)
