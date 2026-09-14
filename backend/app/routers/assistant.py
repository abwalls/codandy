"""Opt-in, loopback-only subscription connection; never forwarded by the hosted proxy."""

import json
from contextlib import contextmanager
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.codex_bridge import CodexUnavailable

router = APIRouter(prefix="/analyses/assistant", tags=["local-assistant"])
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@contextmanager
def connection(request: Request):
    if not request.client or request.client.host not in LOCAL_HOSTS or request.url.hostname not in LOCAL_HOSTS:
        raise HTTPException(403, "The subscription connection is available on this computer only.")
    if request.headers.get("x-codandy-local") != "1" and request.headers.get("x-code-atlas-local") != "1":
        raise HTTPException(403, "Local Atlas client header required.")
    origin = request.headers.get("origin")
    if origin and origin not in {f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in (3000, 5173, 8000)}:
        raise HTTPException(403, "Unapproved browser origin.")
    bridge = getattr(request.app.state, "codex", None)
    if bridge is None:
        raise HTTPException(503, "Enable CODANDY_CODEX_ENABLED on the local backend to connect Codex.")
    if not bridge.lock.acquire(blocking=False):
        raise HTTPException(409, "Codex is handling another request. Wait for it to finish.")
    try:
        yield bridge
    except CodexUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    finally:
        bridge.lock.release()


@router.get("/status")
def status(request: Request):
    with connection(request) as bridge:
        account = bridge.account()
        return {**account, "models": bridge.models() if account["connected"] else []}


@router.post("/login")
def login(request: Request):
    with connection(request) as bridge:
        bridge.start()
        result = bridge.rpc("account/login/start", {"type": "chatgpt"})
        url = result.get("authUrl", "")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "auth.openai.com" or parsed.username or parsed.password:
            raise HTTPException(503, "Codex returned an unsupported login URL.")
        return {"url": url}


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_id: UUID
    question: str = Field(min_length=1, max_length=4000)
    title: str = Field(default="Overview", max_length=250)
    node_ids: list[str] = Field(default_factory=list, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    effort: str = Field(min_length=1, max_length=20)

    @field_validator("question")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1, max_length=30000)
    citations: list[str] = Field(max_length=24)


def grounded_prompt(atlas, question):
    by_id = {node.id: node for node in atlas.nodes}
    if any(node_id not in by_id for node_id in question.node_ids):
        raise HTTPException(422, "Selected evidence is not part of this analysis.")
    ids = list(dict.fromkeys(question.node_ids)) if question.node_ids else [node.id for node in atlas.nodes if node.kind in {"project", "route", "dependency"}]
    selected = [by_id[node_id] for node_id in ids[:24]]
    included = {node.id for node in selected}
    context = {"repository": atlas.repository, "scope": question.title, "counts": atlas.counts,
               "limitations": atlas.limitations[:15], "omitted_nodes": max(0, len(ids) - len(selected)),
               "nodes": [{"id": node.id, "label": node.label[:250], "kind": node.kind, "path": node.path,
                          "detail": node.detail[:600], "evidence": [item.model_dump() for item in node.evidence[:3]]} for node in selected],
               "relationships": [edge.model_dump() for edge in atlas.relationships
                                   if edge.source in included and edge.target in included][:40]}
    prompt = "Question: " + question.question + "\nBounded static graph evidence (no source bodies or live dependency checks):\n" + json.dumps(context)
    if len(prompt.encode()) > 64000:
        raise HTTPException(422, "Selected evidence is too large. Select fewer nodes.")
    return prompt, included


@router.post("/ask", response_model=Answer)
def ask(question: Question, request: Request):
    with connection(request) as bridge:
        atlas = request.app.state.jobs.result(question.analysis_id)
        if atlas is None:
            raise HTTPException(404, "Analysis not found or expired. Reopen a retained report.")
        prompt, included = grounded_prompt(atlas, question)
        if not bridge.account()["connected"]:
            raise HTTPException(409, "Sign in with ChatGPT before asking a question.")
        model = next((item for item in bridge.models() if item["id"] == question.model), None)
        if not model or question.effort not in model["efforts"]:
            raise HTTPException(422, "Refresh the connection and select a supported model and reasoning effort.")
        try:
            result = Answer.model_validate(bridge.answer(prompt, question.model, question.effort))
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(502, "The AI response did not match the required answer format.") from exc
        if any(node_id not in included for node_id in result.citations):
            raise HTTPException(502, "The AI cited evidence outside the supplied context. Please retry.")
        return result
