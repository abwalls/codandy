"""Sentry REST issue-event responses normalized into sanitized observations.

This reads the shape returned by the issue-event API: typed `entries` with camelCase frame
fields (lineNo, colNo, inApp, absPath) and mechanism fields as stored (exception_id,
parent_id, source). SDK ingestion payloads use a different shape (top-level `exception`,
snake_case frames) and are rejected rather than silently reinterpreted.
"""

import itertools
import re
from datetime import datetime

from app.debugging.builder import ObservationBuilder, RawBreadcrumb, RawException, RawFrame
from app.debugging.models import DebuggingLimits, Observation, ObservationSource
from app.debugging.payload import NormalizationError, load_json

_IDENTIFIER = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_SECTION = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}")
_GROUP_MEMBER = re.compile(r"(?:exceptions|errors|InnerExceptions)\[\d{1,6}\]")
_RELATIONS = {"__cause__": "direct_cause", "cause": "direct_cause",
              "__context__": "during_handling", "InnerException": "inner_exception"}
# Sections that can carry personal data, device state or raw request content.
_WITHHELD_KEYS = ("user", "contexts", "context", "packages", "sdk", "userReport", "_meta")
# Local variables, pre-source-map values and provider-supplied URLs are not retained.
_WITHHELD_FRAME_KEYS = ("vars", "mapUrl", "sourceLink", "origAbsPath", "origFilename",
                        "origFunction", "origLineNo", "origColNo")
_EMPTY = (None, "", [], {})

INTERPRETATION = [
    "Sentry orders exception values oldest to newest; the last value surfaced the failure.",
    "Sentry orders frames caller to callee; provider order was kept.",
    ("A relation is set only when mechanism parent_id names the next newer record, or when no "
    "record carries IDs; otherwise provider exception IDs are kept without inferring a relation."),
]


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list:
    return value if isinstance(value, list) else []


def _span(value: object) -> int:
    """Width of a provider [start, end) omission range; 0 when absent or malformed."""
    if (isinstance(value, list) and len(value) == 2 and all(type(n) is int for n in value)
            and 0 <= value[0] < value[1]):
        return value[1] - value[0]
    return 0


def _identifier(value: object) -> str | None:
    if type(value) is int and value >= 0:
        value = str(value)
    return value if isinstance(value, str) and _IDENTIFIER.fullmatch(value) else None


def _timestamp(value: object, name: str, builder: ObservationBuilder) -> datetime | None:
    if value is None:
        return None
    parsed = None
    if isinstance(value, str) and len(value) <= 64:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed = None
    if parsed is None or parsed.tzinfo is None:
        builder.limitations.append(f"An unreadable or timezone-less {name} timestamp was omitted")
        return None
    return parsed


def _relation(source: object) -> str:
    if isinstance(source, str):
        if source in _RELATIONS:
            return _RELATIONS[source]
        if _GROUP_MEMBER.fullmatch(source):
            return "group_member"
    return "chained"


class _EventReader:
    """Tracks withheld sections, malformed items and provider notes while reading entries."""

    def __init__(self, builder: ObservationBuilder):
        self.builder = builder
        self.notes: list[tuple[str, str | None]] = []
        self.malformed = 0

    def withhold(self, name: str):
        self.builder.withheld.append(name)

    def note(self, kind: object, message: object = None):
        if isinstance(kind, str):
            self.notes.append((kind, message if isinstance(message, str) else None))

    def frames(self, stack: dict) -> list[RawFrame]:
        frames = []
        for position, item in enumerate(_items(stack.get("frames"))):
            if not isinstance(item, dict):
                self.malformed += 1
                continue
            for key in _WITHHELD_FRAME_KEYS:
                if item.get(key) not in _EMPTY:
                    self.withhold(f"frame.{key}")
            for error in _items(item.get("errors")):
                kind = error.get("type") if isinstance(error, dict) else None
                if isinstance(kind, str):
                    self.note(f"frame:{kind}")
            context = [(pair[0], pair[1]) for pair in _items(item.get("context"))
                       if isinstance(pair, list) and len(pair) == 2]
            frames.append(RawFrame(
                provider_index=position, function=item.get("function"), module=item.get("module"),
                path=item.get("filename"), abs_path=item.get("absPath"), line=item.get("lineNo"),
                column=item.get("colNo"), in_app=item.get("inApp"), context=context))
        return frames

    def exceptions(self, data: dict) -> list[RawException]:
        records, sources = [], []
        for value in _items(data.get("values")):
            if not isinstance(value, dict):
                self.malformed += 1
                continue
            stack, mechanism = _mapping(value.get("stacktrace")), _mapping(value.get("mechanism"))
            if value.get("rawStacktrace") not in _EMPTY:
                self.withhold("exception.rawStacktrace")
            if stack.get("registers") not in _EMPTY:
                self.withhold("stacktrace.registers")
            if mechanism.get("data") not in _EMPTY or mechanism.get("meta") not in _EMPTY:
                self.withhold("exception.mechanism.data")
            records.append(RawException(
                type=value.get("type"), value=value.get("value"), module=value.get("module"),
                frames=self.frames(stack), frames_omitted=_span(stack.get("framesOmitted")),
                provider_exception_id=mechanism.get("exception_id"),
                provider_parent_id=mechanism.get("parent_id"), handled=mechanism.get("handled")))
            sources.append(mechanism.get("source"))
        has_ids = any(r.provider_exception_id is not None or r.provider_parent_id is not None
                      for r in records)
        for index, (child, parent) in enumerate(itertools.pairwise(records)):
            reference, parent_id = child.provider_parent_id, parent.provider_exception_id
            if not has_ids:
                child.relation_to_next = "chained"
            elif type(reference) is int and type(parent_id) is int and reference == parent_id:
                child.relation_to_next = _relation(sources[index])
        if omitted := _span(data.get("excOmitted")):
            self.builder.limitations.append(
                f"Sentry omitted {omitted} exception value(s) from this event")
        return records

    def breadcrumbs(self, data: dict) -> list[RawBreadcrumb]:
        crumbs = []
        for item in _items(data.get("values")):
            if not isinstance(item, dict):
                self.malformed += 1
                continue
            if item.get("data") not in _EMPTY:
                self.withhold("breadcrumbs.data")
            crumbs.append(RawBreadcrumb(
                timestamp=_timestamp(item.get("timestamp"), "breadcrumb", self.builder),
                type=item.get("type"), category=item.get("category"), level=item.get("level"),
                message=item.get("message")))
        return crumbs


def normalize_sentry_event(payload: object, limits: DebuggingLimits | None = None, *,
                           issue_id: str | None = None,
                           fetched_at: datetime | None = None) -> Observation:
    if not isinstance(payload, dict):
        raise NormalizationError("A Sentry event must be a JSON object")
    if "entries" not in payload and ("exception" in payload or "event_id" in payload):
        raise NormalizationError("This is a Sentry SDK event payload, not a REST issue-event "
                                 "response; SDK payload import is not supported")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise NormalizationError("A Sentry REST event response requires an entries list")
    event_id = _identifier(payload.get("eventID")) or _identifier(payload.get("id"))
    if event_id is None or not re.fullmatch(r"[a-fA-F0-9]{32}", event_id):
        raise NormalizationError("The Sentry event has no valid event identifier")
    group = _identifier(payload.get("groupID"))
    group = group if group and group.isascii() and group.isdecimal() else None
    if issue_id is not None:
        if _identifier(issue_id) is None:
            raise NormalizationError("Invalid Sentry issue identifier")
        if group is not None and group != issue_id:
            raise NormalizationError("The event belongs to a different Sentry issue than requested")
    builder = ObservationBuilder(limits or DebuggingLimits())
    reader = _EventReader(builder)
    exceptions: list[RawException] = []
    breadcrumbs: list[RawBreadcrumb] = []
    message = None
    for entry in entries:
        if not isinstance(entry, dict):
            reader.malformed += 1
            continue
        kind, data = entry.get("type"), _mapping(entry.get("data"))
        if kind == "exception":
            exceptions.extend(reader.exceptions(data))
        elif kind == "breadcrumbs":
            breadcrumbs.extend(reader.breadcrumbs(data))
        elif kind == "message":
            message = data.get("formatted") or data.get("message")
        elif isinstance(kind, str) and _SECTION.fullmatch(kind):
            reader.withhold(f"entry.{kind}")
        else:
            reader.withhold("entry.unrecognized")
    for key in _WITHHELD_KEYS:
        if payload.get(key) not in _EMPTY:
            reader.withhold(key)
    tags = [tag for tag in _items(payload.get("tags")) if isinstance(tag, dict)]
    environment = next((tag.get("value") for tag in tags if tag.get("key") == "environment"), None)
    if any(tag.get("key") != "environment" for tag in tags):
        reader.withhold("tags")
    release = payload.get("release")
    if isinstance(release, dict):
        release = release.get("version")
    for error in _items(payload.get("errors")):
        if isinstance(error, dict):
            reader.note(error.get("type"), error.get("message"))
            if error.get("data") not in _EMPTY:
                reader.withhold("errors.data")
    if reader.malformed:
        builder.limitations.append(f"{reader.malformed} malformed provider item(s) were skipped")
    if not exceptions:
        builder.limitations.append("The event has no exception entry, so no stack is available")
    if isinstance(release, str):
        builder.limitations.append("The release label is not a verified source revision")
    source = ObservationSource(
        provider="sentry", format="sentry_rest_event", event_id=event_id,
        issue_id=group or issue_id, project_id=(_identifier(payload.get("projectID")) if re.fullmatch(
            r"[0-9]{1,32}", str(payload.get("projectID", ""))) else None),
        fetched_at=fetched_at, interpretation=INTERPRETATION)
    occurred = _timestamp(payload.get("dateCreated"), "occurrence", builder)
    received = _timestamp(payload.get("dateReceived"), "received", builder)
    return builder.build(
        source, exceptions, title=payload.get("title"),
        message=message if message else payload.get("message"),
        platform=payload.get("platform"), environment=environment, release=release,
        occurred_at=occurred, received_at=received, breadcrumbs=breadcrumbs,
        notes=list(dict.fromkeys(reader.notes)))


def normalize_sentry_event_bytes(data: bytes, limits: DebuggingLimits | None = None, *,
                                 issue_id: str | None = None,
                                 fetched_at: datetime | None = None) -> Observation:
    """Imported or fetched bytes pass through the same bounded decoder as every payload."""
    limits = limits or DebuggingLimits()
    return normalize_sentry_event(load_json(data, limits), limits, issue_id=issue_id,
                                  fetched_at=fetched_at)
