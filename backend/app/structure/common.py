"""Intermediate declarations shared by the extractors before identities are assigned."""

import hashlib
from dataclasses import dataclass, field

from app.debugging.redaction import Redactor

MAX_NAME = 128
MAX_TYPE_TEXT = 120


def structure_id(kind: str, *parts: str) -> str:
    return f"{kind}:" + hashlib.sha256("\0".join(parts).encode()).hexdigest()[:24]


def clip(text: str, limit: int = MAX_TYPE_TEXT) -> str:
    compact = " ".join(Redactor().text(text, "structure_type").split())
    return compact if len(compact) <= limit else compact[:limit - 1] + "…"


def line_range(start: int, end: int | None = None) -> str:
    return f"{start}-{end if end is not None else start}"


@dataclass
class RawField:
    name: str
    type: str = ""
    primary: bool = False
    unique: bool = False
    foreign: bool = False
    nullable: bool | None = None
    line: int | None = None


@dataclass(eq=False)
class RawEntity:
    name: str
    kind: str
    path: str
    lines: str
    reason: str
    fields: list[RawField] = field(default_factory=list)
    table: str | None = None
    namespace: str | None = None
    # Lookup keys that references in the same schema can use, e.g. "table:users".
    keys: tuple[str, ...] = ()
    more_evidence: list[tuple[str, str, str]] = field(default_factory=list)

    def field_named(self, name: str, *, fold: bool = False) -> RawField | None:
        wanted = name.lower() if fold else name
        return next((item for item in self.fields
                     if (item.name.lower() if fold else item.name) == wanted), None)


@dataclass(eq=False)
class RawLink:
    source: RawEntity
    source_fields: list[str]
    # None means the reference cannot name a declaration, e.g. settings.AUTH_USER_MODEL.
    target_key: str | None
    target_name: str
    target_fields: list[str]
    source_cardinality: str
    target_cardinality: str
    source_optional: bool | None
    target_optional: bool | None
    label: str
    basis: str
    path: str
    lines: str
    reason: str
    target_entity: RawEntity | None = None
    # ORM relation views of a foreign key are dropped when a declared link already joins the pair.
    unless_linked: bool = False


@dataclass(eq=False)
class RawType:
    name: str
    language: str
    kind: str
    path: str
    lines: str
    members: list[tuple[str, str, int]] = field(default_factory=list)
    # (member or None, referenced name, "extends" | "field_type", line)
    references: list[tuple[str | None, str, str, int]] = field(default_factory=list)
