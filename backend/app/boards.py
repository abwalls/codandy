"""Local whiteboards and deterministic reviewed planning packets."""
import hashlib
import json
import math
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.debugging.redaction import Redactor

LIMIT = 4 * 1024 * 1024
TYPES = {"rectangle", "diamond", "ellipse", "text", "arrow", "line", "freedraw", "frame"}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Scene(Contract):
    elements: list[dict] = Field(default_factory=list, max_length=5000)

    @field_validator("elements")
    @classmethod
    def validate_elements(cls, values):
        identifiers = set()
        for e in values:
            identifier = e.get("id")
            if not isinstance(identifier, str) or not 1 <= len(identifier) <= 100 or identifier in identifiers:
                raise ValueError("Every element needs a unique bounded ID")
            identifiers.add(identifier)
            if e.get("type") not in TYPES:
                raise ValueError("Images, embeds and unknown shapes are unsupported")
            if e.get("link") or e.get("customData") or e.get("fileId"):
                raise ValueError("Remove element links, files and custom data before importing")
            for key in ("x", "y", "width", "height", "angle"):
                v = e.get(key, 0)
                if type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 1000000:
                    raise ValueError("Invalid element geometry")
            for key in ("text", "originalText"):
                if key in e and (not isinstance(e[key], str) or len(e[key]) > 2000):
                    raise ValueError("Text elements are limited to 2,000 characters")
            for key in ("groupIds", "points", "pressures", "boundElements"):
                if e.get(key) is not None and (not isinstance(e[key], list) or len(e[key]) > 10000):
                    raise ValueError("Invalid element collection")
            for point in e.get("points", []):
                if not isinstance(point, list) or len(point) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1000000 for v in point):
                    raise ValueError("Invalid drawing point")
            for group in e.get("groupIds", []):
                if not isinstance(group, str) or len(group) > 100:
                    raise ValueError("Invalid group ID")
            for key in ("containerId", "frameId"):
                if e.get(key) is not None and (not isinstance(e[key], str) or len(e[key]) > 100):
                    raise ValueError("Invalid parent ID")
            for key in ("startBinding", "endBinding"):
                binding = e.get(key)
                if binding is not None and (not isinstance(binding, dict) or not isinstance(binding.get("elementId"), str)):
                    raise ValueError("Invalid arrow binding")
        # No arbitrary appState, binary files, libraries or external resources are retained.
        if len(json.dumps(values, allow_nan=False).encode()) > LIMIT:
            raise ValueError("Board exceeds 4 MiB")
        return values


class Draft(Contract):
    title: str = Field(default="Untitled board", min_length=1, max_length=200)
    scene: Scene = Field(default_factory=Scene)
    notes: str = Field(default="", max_length=8000)
    snapshot_id: UUID | None = None


class Edit(Draft):
    revision: int = Field(ge=1)


class Finding(Contract):
    text: str = Field(min_length=1, max_length=2000)
    element_ids: list[str] = Field(max_length=40)
    basis: Literal["drawn", "answered", "assumed"]


class Interpretation(Contract):
    summary: str = Field(min_length=1, max_length=4000)
    findings: list[Finding] = Field(max_length=60)
    questions: list[str] = Field(max_length=8)
    assumptions: list[str] = Field(max_length=30)


class Task(Contract):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=3000)
    depends_on: list[str] = Field(max_length=30)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=12)
    verification: list[str] = Field(min_length=1, max_length=12)
    proposed_paths: list[str] = Field(max_length=20)


class Plan(Contract):
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=4000)
    in_scope: list[str] = Field(max_length=30)
    out_of_scope: list[str] = Field(max_length=30)
    decisions: list[Finding] = Field(max_length=40)
    tasks: list[Task] = Field(min_length=1, max_length=40)
    risks: list[str] = Field(max_length=30)
    open_questions: list[str] = Field(max_length=20)


class Artifact(Contract):
    id: UUID = Field(default_factory=uuid4)
    revision: int
    stage: Literal["interpret", "plan"]
    digest: str
    model: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    interpretation: Interpretation | None = None
    plan: Plan | None = None


class Board(Draft):
    schema_version: Literal["board-0.1"] = "board-0.1"
    id: UUID = Field(default_factory=uuid4)
    revision: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    artifacts: list[Artifact] = Field(default_factory=list, max_length=20)


class Conflict(ValueError):
    pass


class BoardStore:
    def __init__(self, root):
        self.root = Path(root) if root is not None else None
        self.lock = threading.RLock()
        self.items = {}
        self.unreadable = 0
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)
            for path in self.root.glob("*.json"):
                try:
                    if path.is_symlink() or path.stat().st_size > LIMIT:
                        raise ValueError("Invalid board file")
                    board = Board.model_validate_json(path.read_bytes())
                    if path.stem != str(board.id) or len(self.items) >= 200:
                        raise ValueError("Invalid board identity or storage limit")
                    self.items[board.id] = board
                except (ValueError, OSError):
                    self.unreadable += 1

    def get(self, identifier):
        with self.lock:
            return self.items[identifier].model_copy(deep=True)

    def persist(self, board):
        raw = board.model_dump_json().encode()
        if len(raw) > LIMIT:
            raise ValueError("Saved board including plans exceeds 4 MiB")
        if self.root:
            target = self.root / f"{board.id}.json"
            if target.is_symlink():
                raise ValueError("Board storage cannot be a symlink")
            temp = self.root / f"{uuid4()}.tmp"
            try:
                with temp.open("xb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, target)
            finally:
                temp.unlink(missing_ok=True)
        self.items[board.id] = board
        return board.model_copy(deep=True)

    def create(self, draft):
        with self.lock:
            if len(self.items) >= 200:
                raise ValueError("Board limit reached (200); export and delete a board first")
            return self.persist(Board(**draft.model_dump()))

    def update(self, identifier, edit):
        with self.lock:
            board = self.get(identifier)
            if board.revision != edit.revision:
                raise Conflict("This board changed in another tab. Export your draft before reopening it.")
            for key, value in edit.model_dump(exclude={"revision", "scene"}).items():
                setattr(board, key, value)
            board.scene = edit.scene
            board.revision += 1
            board.updated_at = datetime.now(UTC)
            return self.persist(board)

    def add_artifact(self, identifier, artifact):
        with self.lock:
            board = self.get(identifier)
            if board.revision != artifact.revision:
                raise Conflict("Board changed while AI was working. Review and try again.")
            if sum(a.revision == board.revision and a.stage == artifact.stage for a in board.artifacts) >= 5:
                raise ValueError("Five requests per stage and revision are allowed; clarify the board before retrying")
            board.artifacts = [*board.artifacts[-19:], artifact]
            return self.persist(board)

    def delete(self, identifier, revision):
        with self.lock:
            board = self.get(identifier)
            if board.revision != revision:
                raise Conflict("Board changed; reopen it before deleting")
            if self.root:
                (self.root / f"{identifier}.json").unlink()
            del self.items[identifier]


def packet(board, stage, atlas=None):
    redactor = Redactor()
    elements = [e for e in board.scene.elements if not e.get("isDeleted")]
    elements.sort(key=lambda e: (e.get("y", 0), e.get("x", 0), e["id"]))
    ids = {e["id"] for e in elements}
    records = []
    for e in elements:
        item = {"id": e["id"], "type": e["type"], "text": redactor.text(e.get("text", ""), "board"),
                "box": [round(e.get(k, 0), 1) for k in ("x", "y", "width", "height")],
                "container": e.get("containerId"), "frame": e.get("frameId")}
        if e["type"] in {"arrow", "line"}:
            item["ends"] = [(e.get(k) or {}).get("elementId") for k in ("startBinding", "endBinding")]
            item["ends"] = [v if v in ids else None for v in item["ends"]]
            item["arrowheads"] = [e.get("startArrowhead"), e.get("endArrowhead")]
        records.append(item)
    context = {"schema": "board-digest-0.1", "board_id": str(board.id), "revision": board.revision,
               "title": redactor.text(board.title, "title"), "user_answers_and_corrections": redactor.text(board.notes, "notes"),
               "elements": records, "omitted_elements": 0,
               "limitations": ["Drawing expresses user intent, not verified architecture.",
                               "Unlabeled/freehand drawings are not interpreted visually.",
                               "Unbound arrows have unknown endpoints; layout does not prove a connection."],
               "repository": None}
    if atlas:
        context["repository"] = {"snapshot_id": str(board.snapshot_id), "metadata": {k: redactor.text(str(v), "repository") for k, v in atlas.repository.items()},
                                 "files": [redactor.text(n.path or "", "repository") for n in atlas.nodes if n.kind == "file"][:100],
                                 "basis": "indexed snapshot; no source bodies or runtime verification"}
    if stage == "plan":
        prior = next((a for a in reversed(board.artifacts) if a.stage == "interpret" and a.revision == board.revision), None)
        if prior is None:
            raise ValueError("Interpret the current revision before generating a plan")
        context["interpretation"] = prior.interpretation.model_dump()
    while len(json.dumps(context).encode()) > 40000 and records:
        records.pop()
        context["omitted_elements"] += 1
    if len(json.dumps(context).encode()) > 40000:
        raise ValueError("Board notes and interpretation exceed the review budget; shorten them")
    retained = {e["id"] for e in records}
    for item in records:
        if "ends" in item:
            item["ends"] = [identifier if identifier in retained else None for identifier in item["ends"]]
    text = json.dumps(context, sort_keys=True, ensure_ascii=True)
    return {"stage": stage, "revision": board.revision, "digest": hashlib.sha256(text.encode()).hexdigest(),
            "packet": context, "text": text}


def validate_output(value, review):
    allowed = {e["id"] for e in review["packet"]["elements"]}
    findings = value.findings if isinstance(value, Interpretation) else value.decisions
    for finding in findings:
        if any(identifier not in allowed for identifier in finding.element_ids):
            raise ValueError("AI cited an element outside the reviewed packet")
        if finding.basis == "drawn" and not finding.element_ids:
            raise ValueError("Drawn findings require an element citation")
    if isinstance(value, Plan):
        seen = set()
        for task in value.tasks:
            if task.id in seen or any(dep not in seen for dep in task.depends_on):
                raise ValueError("Plan tasks contain duplicate, missing or circular dependencies")
            seen.add(task.id)
    return value


def render_plan(board, artifact, ticket=False):
    p = artifact.plan
    lines = [f"# {p.title}", "", p.objective, "", f"Board {board.id} · revision {artifact.revision} · {artifact.model}",
             f"Generated {artifact.created_at.isoformat()}. AI proposal; review before implementation.", ""]
    if artifact.revision != board.revision:
        lines += ["STALE: the board has changed since this plan was generated.", ""]
    for heading, values in (("In scope", p.in_scope), ("Out of scope", p.out_of_scope)):
        lines += [f"## {heading}", "", *[f"- {v}" for v in values], ""]
    lines += ["## Decisions", "", *[f"- [{d.basis}] {d.text} (elements: {', '.join(d.element_ids) or 'none'})" for d in p.decisions], ""]
    for task in p.tasks:
        lines += [f"## {'[ ] ' if ticket else ''}{task.id}: {task.title}", "", task.description,
                  f"Depends on: {', '.join(task.depends_on) or 'none'}", "",
                  *[f"- [ ] {v}" for v in task.acceptance_criteria], "",
                  "Verification:", *[f"- {v}" for v in task.verification], "",
                  "Proposed paths (existence unverified):", *[f"- {v}" for v in task.proposed_paths], ""]
    lines += ["## Risks", "", *[f"- {v}" for v in p.risks], "", "## Open questions", "",
              *[f"- {v}" for v in p.open_questions], "",
              "Items marked assumed or proposed are unverified; confirm them before implementing."]
    return "\n".join(lines)
