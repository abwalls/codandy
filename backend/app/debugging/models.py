"""Versioned debugging contracts, kept separate from the static atlas (schema 0.2).

Observations hold sanitized, bounded provider evidence, and absent provider values stay
absent rather than guessed. A binding associates one observed frame with a pinned
snapshot and states how certain that association is. Nothing here mutates the atlas.
"""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "debugging-0.1"


def _now() -> datetime:
    return datetime.now(UTC)


def is_repository_relative(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return (bool(path) and not any(ord(c) < 32 or ord(c) == 127 for c in path)
            and not path.startswith(("/", "\\")) and ":" not in path
            and all(part not in {"", ".", ".."} for part in parts))


class Contract(BaseModel):
    # Persisted and restored documents must not carry unvalidated fields.
    model_config = ConfigDict(extra="forbid")


class DebuggingLimits(Contract):
    """Initial engineering bounds from PLAN.md D1. Tunable; these are not provider limits."""

    max_payload_bytes: int = Field(default=2 * 1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    max_json_depth: int = Field(default=32, ge=4, le=128)
    max_frames: int = Field(default=200, ge=1, le=2000)
    max_exceptions: int = Field(default=20, ge=1, le=100)
    max_breadcrumbs: int = Field(default=200, ge=0, le=1000)
    max_context_lines: int = Field(default=11, ge=0, le=41)
    max_provider_notes: int = Field(default=20, ge=0, le=200)
    max_text_chars: int = Field(default=2000, ge=80, le=20_000)
    max_line_chars: int = Field(default=500, ge=80, le=4096)


class ContextLine(Contract):
    line: int = Field(ge=1)
    text: str


class StackFrame(Contract):
    # Normalized order is caller to callee: index 0 is the oldest frame and the last
    # frame is where the exception was raised. provider_index keeps the input position.
    index: int = Field(ge=0)
    provider_index: int = Field(ge=0)
    function: str | None = None
    module: str | None = None
    path: str | None = None
    abs_path: str | None = None
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=0)
    in_app: bool | None = None
    after_async_boundary: bool = False
    context: list[ContextLine] = Field(default_factory=list)


class ExceptionRecord(Contract):
    # Records are ordered oldest to newest; the last record is the exception that surfaced.
    # relation_to_next is this record's role for the next newer record, e.g. it was the
    # direct cause of that exception, or that exception wrapped it as an inner exception.
    index: int = Field(ge=0)
    type: str | None = None
    value: str | None = None
    module: str | None = None
    relation_to_next: Literal["direct_cause", "during_handling", "inner_exception",
                              "group_member", "chained"] | None = None
    provider_exception_id: int | None = None
    provider_parent_id: int | None = None
    handled: bool | None = None
    frames: list[StackFrame] = Field(default_factory=list)
    frames_omitted: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_frames(self):
        if [frame.index for frame in self.frames] != list(range(len(self.frames))):
            raise ValueError("Frames must be indexed oldest caller first without gaps")
        if len({frame.provider_index for frame in self.frames}) != len(self.frames):
            raise ValueError("Duplicate provider frame position")
        return self


class Breadcrumb(Contract):
    timestamp: datetime | None = None
    type: str | None = None
    category: str | None = None
    level: str | None = None
    message: str | None = None


class ProviderNote(Contract):
    """Provider processing errors, e.g. a missing source map; kept as evidence gaps."""

    type: str
    message: str | None = None


class Truncation(Contract):
    # Item counts for collections; character counts for clipped text sections.
    section: str
    reason: str
    original: int = Field(ge=0)
    retained: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self):
        if self.retained >= self.original:
            raise ValueError("A truncation must retain less than the original")
        return self


class RedactionCount(Contract):
    section: str
    kind: str
    count: int = Field(ge=1)


class ObservationSource(Contract):
    provider: Literal["sentry", "pasted"]
    format: Literal["sentry_rest_event", "python_traceback", "javascript_stack", "dotnet_stack"]
    event_id: str | None = None
    issue_id: str | None = None
    project_id: str | None = None
    fetched_at: datetime | None = None
    # How the adapter interpreted ordering and chaining, stated rather than implied.
    interpretation: list[str] = Field(default_factory=list)


class Observation(Contract):
    schema_version: Literal["debugging-0.1"] = SCHEMA_VERSION
    id: UUID = Field(default_factory=uuid4)
    kind: Literal["exception"] = "exception"
    source: ObservationSource
    normalized_at: datetime = Field(default_factory=_now)
    occurred_at: datetime | None = None
    received_at: datetime | None = None
    title: str | None = None
    message: str | None = None
    platform: str | None = None
    environment: str | None = None
    # A release label as reported. It never implies a Git revision.
    release: str | None = None
    exceptions: list[ExceptionRecord] = Field(default_factory=list)
    breadcrumbs: list[Breadcrumb] = Field(default_factory=list)
    provider_notes: list[ProviderNote] = Field(default_factory=list)
    truncations: list[Truncation] = Field(default_factory=list)
    redactions: list[RedactionCount] = Field(default_factory=list)
    # Provider sections deliberately not retained, such as request data or frame variables.
    withheld: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_structure(self):
        if (self.source.provider == "sentry") != (self.source.format == "sentry_rest_event"):
            raise ValueError("Observation provider and format disagree")
        if [record.index for record in self.exceptions] != list(range(len(self.exceptions))):
            raise ValueError("Exception records must be indexed oldest first without gaps")
        if self.exceptions and self.exceptions[-1].relation_to_next is not None:
            raise ValueError("The newest exception cannot relate to a later record")
        return self


class BindingCandidate(Contract):
    path: str
    line: int | None = Field(default=None, ge=1)
    node_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_path(self):
        # Candidates address captured snapshot paths, never telemetry-supplied locations.
        if not is_repository_relative(self.path):
            raise ValueError("Binding candidates must be repository-relative snapshot paths")
        return self


class SourceBinding(Contract):
    schema_version: Literal["debugging-0.1"] = SCHEMA_VERSION
    observation_id: UUID
    exception_index: int = Field(ge=0)
    frame_index: int = Field(ge=0)
    snapshot_id: UUID
    status: Literal["exact", "candidate", "ambiguous", "unmapped"]
    method: Literal["path_mapping", "exact_path", "path_suffix", "basename", "function_name",
                    "none"]
    revision: Literal["verified", "mismatch", "unknown"]
    candidates: list[BindingCandidate] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_certainty(self):
        count = len(self.candidates)
        if len({(c.path, c.line) for c in self.candidates}) != count:
            raise ValueError("Duplicate binding candidate")
        if (self.status == "unmapped") != (self.method == "none"):
            raise ValueError("Only unmapped bindings have no mapping method")
        if self.status == "unmapped" and count:
            raise ValueError("Unmapped bindings cannot carry candidates")
        if self.status == "candidate" and count != 1:
            raise ValueError("A candidate binding has exactly one candidate")
        if self.status == "ambiguous" and count < 2:
            raise ValueError("Ambiguous bindings require competing candidates")
        if self.status == "exact":
            # Exact means a verified revision plus a known line, not a plausible path.
            if count != 1 or self.candidates[0].line is None or self.revision != "verified":
                raise ValueError("Exact bindings need one line-level candidate at a verified revision")
            if self.method in {"basename", "function_name"}:
                raise ValueError("A basename or function name alone cannot be exact")
        return self


class InvestigationNote(Contract):
    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=_now)
    text: str = Field(min_length=1, max_length=20_000)


class Investigation(Contract):
    schema_version: Literal["debugging-0.1"] = SCHEMA_VERSION
    id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=200)
    state: Literal["open", "resolved", "archived"] = "open"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    observation_ids: list[UUID] = Field(default_factory=list)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    bindings: list[SourceBinding] = Field(default_factory=list)
    notes: list[InvestigationNote] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self):
        observations, snapshots = set(self.observation_ids), set(self.snapshot_ids)
        if len(observations) != len(self.observation_ids) or len(snapshots) != len(self.snapshot_ids):
            raise ValueError("Duplicate investigation reference")
        keys = set()
        for binding in self.bindings:
            if binding.observation_id not in observations or binding.snapshot_id not in snapshots:
                raise ValueError("Binding references evidence outside this investigation")
            key = (binding.observation_id, binding.exception_index, binding.frame_index,
                   binding.snapshot_id)
            if key in keys:
                raise ValueError("Duplicate binding for one frame and snapshot")
            keys.add(key)
        if self.updated_at < self.created_at:
            raise ValueError("Investigation updated before it was created")
        return self
