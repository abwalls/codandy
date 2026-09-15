"""Bounded OTLP JSON trace imports. No collector, provider calls or code execution."""
import re
from typing import Literal

from pydantic import Field

from app.debugging.models import Contract, DebuggingLimits, RedactionCount
from app.debugging.payload import NormalizationError, load_json
from app.debugging.redaction import Redactor

MAX_SPANS = 1000


class TraceSpan(Contract):
    trace_id: str
    span_id: str
    parent_id: str | None
    name: str
    service: str
    start_ns: str
    end_ns: str
    status: Literal["unset", "ok", "error"]
    parent_state: Literal["root", "present", "missing", "cycle"] = "root"
    attributes: dict[str, str] = Field(default_factory=dict)


class TraceImport(Contract):
    schema_version: Literal["trace-0.1"] = "trace-0.1"
    spans: list[TraceSpan] = Field(max_length=MAX_SPANS)
    omitted_spans: int = 0
    withheld_attributes: int = 0
    redactions: list[RedactionCount] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: [
        "Imported span wall time is not CPU time; overlapping durations must not be added.",
        "This file may contain a partial trace. Parent relationships are provider-reported, not source-code calls.",
        "Span events, links, resource metadata other than service.name, and unapproved attributes are withheld.",
        "No live monitoring, source binding, exception conversion or automatic AI submission occurs.",
    ])


def identifier(value, length):
    if not isinstance(value, str) or not re.fullmatch(f"[a-fA-F0-9]{{{length}}}", value) or int(value, 16) == 0:
        raise NormalizationError("OTLP IDs must be nonzero hexadecimal trace/span IDs")
    return value.lower()


def nanos(value):
    if type(value) not in (str, int) or not re.fullmatch(r"[0-9]{1,20}", str(value)):
        raise NormalizationError("OTLP timestamps must be unsigned integer nanoseconds")
    number = int(value)
    if number > 2**64 - 1:
        raise NormalizationError("OTLP timestamp exceeds uint64 range")
    return number


def objects(value, section):
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise NormalizationError(f"Invalid OTLP {section} collection")
    return value


def normalize_trace_bytes(data):
    raw = load_json(data, DebuggingLimits())
    if not isinstance(raw, dict) or "resourceSpans" not in raw:
        raise NormalizationError("Use OTLP JSON with resourceSpans (not protobuf or a provider export)")
    spans, seen, redactor = [], set(), Redactor()
    omitted = withheld = 0
    allowed = {"code.file.path", "code.filepath", "code.function.name", "code.function", "code.namespace", "code.line.number", "code.lineno", "http.request.method", "http.method", "http.response.status_code", "http.status_code", "db.system.name", "db.system"}

    def clean(value, fallback=""):
        return redactor.text(value, "trace")[:500] if isinstance(value, str) else fallback

    for resource in objects(raw["resourceSpans"], "resourceSpans"):
        metadata = resource.get("resource", {})
        if not isinstance(metadata, dict):
            raise NormalizationError("Invalid OTLP resource")
        service = "Unknown service"
        for attribute in objects(metadata.get("attributes", []), "resource attributes"):
            value = attribute.get("value", {})
            if attribute.get("key") == "service.name" and isinstance(value, dict):
                service = clean(value.get("stringValue"), "Unknown service")
            else:
                withheld += 1
        for scope in objects(resource.get("scopeSpans", []), "scopeSpans"):
            for span in objects(scope.get("spans", []), "spans"):
                if len(spans) >= MAX_SPANS:
                    omitted += 1
                    continue
                trace_id, span_id = identifier(span.get("traceId"), 32), identifier(span.get("spanId"), 16)
                if (trace_id, span_id) in seen:
                    raise NormalizationError("Duplicate span IDs within a trace are ambiguous; import one copy")
                seen.add((trace_id, span_id))
                parent = span.get("parentSpanId")
                parent = identifier(parent, 16) if parent not in (None, "", "0" * 16) else None
                start, end = nanos(span.get("startTimeUnixNano")), nanos(span.get("endTimeUnixNano"))
                if end < start:
                    raise NormalizationError("A span ends before it starts")
                status = span.get("status", {})
                if not isinstance(status, dict) or type(status.get("code", 0)) is not int or status.get("code", 0) not in (0, 1, 2):
                    raise NormalizationError("OTLP status code must be 0, 1 or 2")
                attributes = {}
                for attribute in objects(span.get("attributes", []), "span attributes"):
                    key, value = attribute.get("key"), attribute.get("value", {})
                    if isinstance(key, str) and key in allowed and isinstance(value, dict):
                        candidate = value.get("stringValue", value.get("intValue"))
                        if type(candidate) in (str, int):
                            attributes[key] = clean(str(candidate))
                    else:
                        withheld += 1
                spans.append(TraceSpan(trace_id=trace_id, span_id=span_id, parent_id=parent,
                                       name=clean(span.get("name"), "Unnamed span"), service=service,
                                       start_ns=str(start), end_ns=str(end), status=("unset", "ok", "error")[status.get("code", 0)],
                                       attributes=attributes))
    if not spans:
        raise NormalizationError("The OTLP file contains no spans")
    by_id = {(s.trace_id, s.span_id): s for s in spans}
    for span in spans:
        if not span.parent_id:
            continue
        span.parent_state = "present" if (span.trace_id, span.parent_id) in by_id else "missing"
        path, current = {span.span_id}, span
        while current.parent_id and (parent := by_id.get((span.trace_id, current.parent_id))):
            if parent.span_id in path:
                span.parent_state = "cycle"
                break
            path.add(parent.span_id)
            current = parent
    return TraceImport(spans=sorted(spans, key=lambda s: (s.trace_id, int(s.start_ns), s.span_id)),
                       omitted_spans=omitted, withheld_attributes=withheld, redactions=redactor.summary())
