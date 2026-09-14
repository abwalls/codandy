"""Single-process local cases; only server-normalized observations can be saved."""

import os
import tempfile
import threading
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from app.debugging.models import Contract, Observation, SourceBinding
from app.debugging.redaction import Redactor

MAX_CASE_BYTES = 4 * 1024 * 1024
MAX_CASES = 100
MAX_PENDING = 20


class SavedCase(Contract):
    schema_version: Literal["case-0.1"] = "case-0.1"
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    state: Literal["open", "resolved", "archived"] = "open"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notes: str = Field(default="", max_length=20000)
    observation: Observation
    snapshot_id: UUID | None = None
    snapshot_repository: dict[str, str] = Field(default_factory=dict)
    runtime_commit: str | None = None
    path_prefix: str = ""
    bindings: list[SourceBinding] = Field(default_factory=list)


    @model_validator(mode="after")
    def validate_bindings(self):
        if self.updated_at < self.created_at:
            raise ValueError("Investigation timestamps are inconsistent")
        keys = set()
        for binding in self.bindings:
            if binding.observation_id != self.observation.id or binding.snapshot_id != self.snapshot_id:
                raise ValueError("Source binding references evidence outside this case")
            if binding.exception_index >= len(self.observation.exceptions):
                raise ValueError("Source binding references a missing exception")
            if binding.frame_index >= len(self.observation.exceptions[binding.exception_index].frames):
                raise ValueError("Source binding references a missing frame")
            key = (binding.exception_index, binding.frame_index)
            if key in keys:
                raise ValueError("Duplicate frame binding")
            keys.add(key)
        return self


class CaseStore:
    def __init__(self, root: str | Path | None):
        self.root = Path(root).resolve() if root else None
        self.lock = threading.RLock()
        self.pending: OrderedDict[UUID, Observation] = OrderedDict()
        self.cases: dict[UUID, SavedCase] = {}
        self.unreadable = 0
        if self.root:
            self.root.mkdir(parents=True, exist_ok=True)
            for path in self.root.glob("*.json"):
                try:
                    identifier = UUID(path.stem)
                    if path.is_symlink() or path.stat().st_size > MAX_CASE_BYTES:
                        raise ValueError("Unsafe case file")
                    case = SavedCase.model_validate_json(path.read_bytes())
                    if case.id != identifier or case.updated_at < case.created_at:
                        raise ValueError("Invalid case identity or timestamps")
                    if len(self.cases) >= MAX_CASES:
                        raise ValueError("Case limit reached")
                    self.cases[case.id] = case
                except (OSError, ValueError):
                    self.unreadable += 1

    def remember(self, observation: Observation) -> Observation:
        with self.lock:
            self.pending[observation.id] = observation.model_copy(deep=True)
            while len(self.pending) > MAX_PENDING:
                self.pending.popitem(last=False)
        return observation

    def listing(self):
        with self.lock:
            return {"persistent": self.root is not None, "unreadable": self.unreadable,
                    "limit": MAX_CASES, "cases": [
                        {"id": str(c.id), "title": c.title, "state": c.state,
                         "created_at": c.created_at, "updated_at": c.updated_at,
                         "provider": c.observation.source.provider}
                        for c in sorted(self.cases.values(), key=lambda c: c.updated_at, reverse=True)]}

    def get(self, identifier: UUID) -> SavedCase:
        with self.lock:
            if identifier not in self.cases:
                raise KeyError("Investigation not found")
            return self.cases[identifier].model_copy(deep=True)

    def save(self, observation_id: UUID) -> SavedCase:
        with self.lock:
            # Repeated Save clicks are idempotent; a later fetch has its own observation ID.
            for case in self.cases.values():
                if case.observation.id == observation_id:
                    return case.model_copy(deep=True)
            if observation_id not in self.pending:
                raise KeyError("Observation expired; import or fetch the evidence again")
            if len(self.cases) >= MAX_CASES:
                raise ValueError("Investigation limit reached; delete an unneeded case first")
            observation = self.pending[observation_id]
            case = SavedCase(title=(observation.title or "Untitled investigation")[:200],
                             observation=observation.model_copy(deep=True))
            self._write(case)
            self.cases[case.id] = case
            return case.model_copy(deep=True)

    def update(self, identifier: UUID, title: str, state: str, notes: str) -> SavedCase:
        with self.lock:
            case = self.get(identifier)
            redactor = Redactor()
            clean_title = redactor.text(title, "case_title").strip()
            if not clean_title:
                raise ValueError("Investigation title cannot be blank")
            case.title = clean_title[:200]
            case.notes = redactor.text(notes, "case_notes")[:20000]
            case.state = state
            case.updated_at = datetime.now(UTC)
            case = SavedCase.model_validate(case.model_dump())
            self._write(case)
            self.cases[case.id] = case
            return case.model_copy(deep=True)

    def bind(self, identifier, atlas, snapshot_id, runtime_commit, path_prefix):
        from app.debugging.bindings import bind_observation
        with self.lock:
            case = self.get(identifier)
            prefix = Redactor().text(path_prefix, "path_prefix")[:500]
            case.bindings = bind_observation(case.observation, atlas, snapshot_id, runtime_commit, prefix)
            case.snapshot_id = snapshot_id
            case.snapshot_repository = dict(atlas.repository)
            case.runtime_commit = runtime_commit
            case.path_prefix = prefix
            case.updated_at = datetime.now(UTC)
            self._write(case)
            self.cases[case.id] = case
            return case.model_copy(deep=True)

    def delete(self, identifier: UUID):
        with self.lock:
            self.get(identifier)
            if self.root:
                (self.root / f"{identifier}.json").unlink(missing_ok=True)
            del self.cases[identifier]

    def _write(self, case: SavedCase):
        data = case.model_dump_json().encode("utf-8")
        if len(data) > MAX_CASE_BYTES:
            raise ValueError("Investigation exceeds the storage budget")
        if not self.root:
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=self.root, suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root / f"{case.id}.json")
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
