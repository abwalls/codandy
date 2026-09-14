"""Shared assembly of bounded, redacted observations for every input format.

Adapters translate their format into raw records already ordered oldest caller first and
state how they read it. This builder applies one set of budgets and one redaction pass,
so pasted, imported and live provider evidence all cross the same boundary.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from app.debugging.models import (
    Breadcrumb,
    ContextLine,
    DebuggingLimits,
    ExceptionRecord,
    Observation,
    ObservationSource,
    ProviderNote,
    StackFrame,
    Truncation,
)
from app.debugging.redaction import Redactor

MAX_POSITION = 2**31 - 1


@dataclass
class RawFrame:
    # Values are untrusted until the builder validates them.
    provider_index: int
    function: object = None
    module: object = None
    path: object = None
    abs_path: object = None
    line: object = None
    column: object = None
    in_app: object = None
    after_async_boundary: bool = False
    context: list[tuple[object, object]] = field(default_factory=list)


@dataclass
class RawException:
    type: object = None
    value: object = None
    module: object = None
    frames: list[RawFrame] = field(default_factory=list)
    frames_omitted: int = 0
    relation_to_next: str | None = None
    provider_exception_id: object = None
    provider_parent_id: object = None
    handled: object = None


@dataclass
class RawBreadcrumb:
    timestamp: datetime | None = None
    type: object = None
    category: object = None
    level: object = None
    message: object = None


def whole_number(value: object, minimum: int) -> int | None:
    # bool is an int subclass: a provider's JSON true must not become line 1.
    return value if type(value) is int and minimum <= value <= MAX_POSITION else None


def flag(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


class ObservationBuilder:
    def __init__(self, limits: DebuggingLimits):
        self.limits = limits
        self.redactor = Redactor()
        self.truncations: list[Truncation] = []
        self.withheld: list[str] = []
        self.limitations: list[str] = []
        self._clipped_original: Counter[str] = Counter()
        self._clipped_retained: Counter[str] = Counter()
        self._context_original = 0
        self._context_retained = 0

    def text(self, value: object, section: str, *, long: bool = False) -> str | None:
        if not isinstance(value, str):
            return None
        # Redact before clipping so a cut can never leave an unrecognizable secret fragment.
        cleaned = self.redactor.text(value, section)
        maximum = self.limits.max_text_chars if long else self.limits.max_line_chars
        if len(cleaned) > maximum:
            self._clipped_original[section] += len(cleaned)
            self._clipped_retained[section] += maximum
            cleaned = cleaned[:maximum]
        return cleaned or None

    def keep_newest(self, items: list, maximum: int, section: str, reason: str) -> list:
        if len(items) <= maximum:
            return items
        self.truncations.append(Truncation(section=section, reason=reason, original=len(items),
                                           retained=maximum))
        return items[len(items) - maximum:]

    def frame(self, index: int, raw: RawFrame) -> StackFrame:
        line = whole_number(raw.line, 1)
        context = [(number, text) for number, text in raw.context
                   if whole_number(number, 1) is not None and isinstance(text, str)]
        self._context_original += len(context)
        if len(context) > self.limits.max_context_lines:
            # Lines nearest the reported line are the evidence; the rest are not needed.
            anchor = line or context[len(context) // 2][0]
            nearest = sorted(context, key=lambda entry: (abs(entry[0] - anchor), entry[0]))
            context = sorted(nearest[:self.limits.max_context_lines])
        self._context_retained += len(context)
        return StackFrame(
            index=index, provider_index=raw.provider_index,
            function=self.text(raw.function, "frame_function"),
            module=self.text(raw.module, "frame_module"),
            path=self.text(raw.path, "frame_path"),
            abs_path=self.text(raw.abs_path, "frame_path"),
            line=line, column=whole_number(raw.column, 0), in_app=flag(raw.in_app),
            after_async_boundary=raw.after_async_boundary,
            context=[ContextLine(line=number, text=self.text(text, "frame_context") or "")
                     for number, text in context])

    def exceptions(self, raw: list[RawException]) -> list[ExceptionRecord]:
        raw = self.keep_newest(raw, self.limits.max_exceptions, "exceptions",
                               "Kept the newest exception records in the chain")
        # Newer exceptions surfaced the failure, so they receive the frame budget first;
        # within a record, the frames nearest the raise point are kept.
        budget = self.limits.max_frames
        kept: list[list[RawFrame]] = []
        for item in reversed(raw):
            frames = item.frames[len(item.frames) - budget:] if budget else []
            budget -= len(frames)
            kept.append(frames)
        kept.reverse()
        original = sum(len(item.frames) for item in raw)
        retained = sum(map(len, kept))
        if retained < original:
            self.truncations.append(Truncation(
                section="frames", reason="Kept frames nearest each raise point, newest exceptions first",
                original=original, retained=retained))
        last = len(raw) - 1
        return [ExceptionRecord(
            index=index,
            type=self.text(item.type, "exception_type"),
            value=self.text(item.value, "exception_value", long=True),
            module=self.text(item.module, "exception_module"),
            relation_to_next=item.relation_to_next if index < last else None,
            provider_exception_id=whole_number(item.provider_exception_id, 0),
            provider_parent_id=whole_number(item.provider_parent_id, 0),
            handled=flag(item.handled),
            frames=[self.frame(position, frame) for position, frame in enumerate(frames)],
            frames_omitted=max(0, item.frames_omitted) + len(item.frames) - len(frames),
        ) for index, (item, frames) in enumerate(zip(raw, kept, strict=True))]

    def breadcrumbs(self, raw: list[RawBreadcrumb]) -> list[Breadcrumb]:
        raw = self.keep_newest(raw, self.limits.max_breadcrumbs, "breadcrumbs",
                               "Kept the most recent breadcrumbs")
        return [Breadcrumb(timestamp=item.timestamp, type=self.text(item.type, "breadcrumb_type"),
                           category=self.text(item.category, "breadcrumb_category"),
                           level=self.text(item.level, "breadcrumb_level"),
                           message=self.text(item.message, "breadcrumb_message", long=True))
                for item in raw]

    def notes(self, raw: list[tuple[object, object]]) -> list[ProviderNote]:
        kept = []
        for kind, message in raw:
            if name := self.text(kind, "provider_note"):
                kept.append(ProviderNote(type=name,
                                         message=self.text(message, "provider_note", long=True)))
        return self.keep_newest(kept, self.limits.max_provider_notes, "provider_notes",
                                "Kept the most recent provider processing notes")

    def build(self, source: ObservationSource, exceptions: list[RawException], *,
              title: object = None, message: object = None, platform: object = None,
              environment: object = None, release: object = None,
              occurred_at: datetime | None = None, received_at: datetime | None = None,
              breadcrumbs: list[RawBreadcrumb] | None = None,
              notes: list[tuple[object, object]] | None = None) -> Observation:
        records = self.exceptions(list(exceptions))
        crumbs = self.breadcrumbs(list(breadcrumbs or []))
        provider_notes = self.notes(list(notes or []))
        values = {"title": self.text(title, "title", long=True),
                  "message": self.text(message, "message", long=True),
                  "platform": self.text(platform, "platform"),
                  "environment": self.text(environment, "environment"),
                  "release": self.text(release, "release")}
        # Clipping totals are only complete once every text value has been processed.
        if self._context_retained < self._context_original:
            self.truncations.append(Truncation(
                section="frame_context", reason="Kept source context lines nearest each reported line",
                original=self._context_original, retained=self._context_retained))
        for section in sorted(self._clipped_original):
            self.truncations.append(Truncation(
                section=section, reason="Text clipped to the character budget (characters)",
                original=self._clipped_original[section], retained=self._clipped_retained[section]))
        return Observation(source=source, occurred_at=occurred_at, received_at=received_at,
                           exceptions=records, breadcrumbs=crumbs, provider_notes=provider_notes,
                           truncations=self.truncations, redactions=self.redactor.summary(),
                           withheld=sorted(set(self.withheld)),
                           limitations=list(dict.fromkeys(self.limitations)), **values)
