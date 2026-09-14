"""Explicit save/reopen/update/delete for sanitized local investigations."""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field

from app.debugging.cases import SavedCase
from app.debugging.models import Contract
from app.routers.debugging import local_only

router = APIRouter(prefix="/debugging/cases", tags=["investigations"],
                   dependencies=[Depends(local_only)])


class SaveCase(Contract):
    observation_id: UUID


class EditCase(Contract):
    title: str = Field(min_length=1, max_length=200)
    state: Literal["open", "resolved", "archived"]
    notes: str = Field(default="", max_length=20000)


def perform(request: Request, method: str, *args):
    try:
        return getattr(request.app.state.investigations, method)(*args)
    except KeyError as exc:
        raise HTTPException(404, exc.args[0]) from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    except OSError:
        raise HTTPException(503, "Could not write local investigation storage; nothing was changed") from None


@router.get("")
def listing(request: Request):
    return perform(request, "listing")


@router.post("", response_model=SavedCase)
def save(body: SaveCase, request: Request):
    return perform(request, "save", body.observation_id)


@router.get("/{identifier}", response_model=SavedCase)
def get(identifier: UUID, request: Request):
    return perform(request, "get", identifier)


@router.put("/{identifier}", response_model=SavedCase)
def update(identifier: UUID, body: EditCase, request: Request):
    return perform(request, "update", identifier, body.title, body.state, body.notes)


@router.delete("/{identifier}", status_code=204)
def delete(identifier: UUID, request: Request):
    perform(request, "delete", identifier)
    return Response(status_code=204)


class BindCase(Contract):
    snapshot_id: UUID
    runtime_commit: str | None = Field(default=None, pattern=r"^(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})$")
    path_prefix: str = Field(default="", max_length=500)


@router.put("/{identifier}/source-binding", response_model=SavedCase)
def bind(identifier: UUID, body: BindCase, request: Request):
    atlas = request.app.state.jobs.result(body.snapshot_id)
    if atlas is None:
        raise HTTPException(404, "Snapshot source has expired or is unavailable; select a retained report")
    return perform(request, "bind", identifier, atlas, body.snapshot_id, body.runtime_commit, body.path_prefix)


@router.get("/{identifier}/brief")
def brief(identifier: UUID, request: Request):
    from app.debugging.brief import build_brief
    case = perform(request, "get", identifier)
    try:
        return build_brief(case)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


class CaseQuestion(Contract):
    question: str = Field(min_length=1, max_length=4000)
    model: str = Field(min_length=1, max_length=100)
    effort: str = Field(min_length=1, max_length=20)
    review_digest: str = Field(pattern=r"^[a-f0-9]{64}$")


@router.post("/{identifier}/ask")
def ask(identifier: UUID, body: CaseQuestion, request: Request):
    from app.debugging.brief import build_brief
    from app.debugging.redaction import Redactor
    from app.routers.assistant import Answer, connection
    case = perform(request, "get", identifier)
    packet = build_brief(case)
    if packet["review_digest"] != body.review_digest:
        raise HTTPException(409, "The saved case changed. Prepare and review a fresh brief before asking.")
    question = Redactor().text(body.question, "question").strip()
    if not question:
        raise HTTPException(422, "Question cannot be blank")
    with connection(request) as bridge:
        if not bridge.account()["connected"]:
            raise HTTPException(409, "Sign in with ChatGPT before asking a question")
        model = next((item for item in bridge.models() if item["id"] == body.model), None)
        if not model or body.effort not in model["efforts"]:
            raise HTTPException(422, "Refresh the connection and choose a supported model and effort")
        prompt = "User question: " + question + "\n\n" + packet["prompt"]
        if len(prompt.encode()) > 68000:
            raise HTTPException(422, "Debugging question exceeds the context budget")
        try:
            answer = Answer.model_validate(bridge.answer(prompt, body.model, body.effort))
        except (ValueError, KeyError, TypeError):
            raise HTTPException(502, "AI response did not match the required answer format") from None
        included = {item["id"] for item in packet["packet"]["evidence"]}
        if any(citation not in included for citation in answer.citations):
            raise HTTPException(502, "AI cited evidence outside the reviewed brief; retry the question")
        return answer
