"""Reviewed payloads and durable at-most-one submission per review/key.

An interrupted or uncertain submission is never retried automatically. SQLite records
contain digests and receipts, never the draft body or provider credentials.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.debugging.models import Contract
from app.debugging.redaction import Redactor
from app.integrations import linear


class Draft(Contract):
    title: str = Field(min_length=1, max_length=250)
    description: str = Field(max_length=16000)
    team_id: UUID
    source_kind: Literal["manual", "board", "recommendation", "case"] = "manual"
    source_id: str = Field(default="", max_length=2048)


class Source(Contract):
    source_kind: Literal["manual", "board", "recommendation", "case"]
    source_id: str = Field(min_length=1, max_length=2048)


def source_digest(source):
    return hashlib.sha256(f"{source.source_kind}:{source.source_id}".encode()).hexdigest()


class Submission(Draft):
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: UUID
    confirmed: Literal[True]
    acknowledge_existing: bool = False


def review(config, draft):
    redactor = Redactor()
    credential = linear.key(config)
    title = redactor.text(draft.title.replace(credential, "[redacted:credential]"), "title").strip()
    if not title:
        raise ValueError("Enter a ticket title")
    payload = {"teamId": str(draft.team_id), "title": title,
               "description": redactor.text(draft.description.replace(credential, "[redacted:credential]"), "description")}
    # Changing accounts, source provenance, target or content invalidates the review.
    account = hashlib.sha256(linear.key(config).encode()).hexdigest()
    envelope = {"provider": "linear", "payload": payload, "account": account,
                "source_kind": draft.source_kind, "source_id": draft.source_id}
    digest = hashlib.sha256(json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"schema_version": "ticket-review-0.1", "provider": "linear", "payload": payload,
            "digest": digest, "redactions": sum(row.count for row in redactor.summary())}


class TicketConflict(ValueError):
    pass


class TicketStore:
    def __init__(self, root):
        self.path = None
        if root:
            location = Path(root)
            location.mkdir(parents=True, exist_ok=True)
            self.path = location / "tickets.sqlite3"
            with self.connect() as db:
                db.execute("CREATE TABLE IF NOT EXISTS submissions (key TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, "
                           "target TEXT NOT NULL, source TEXT NOT NULL, state TEXT NOT NULL, receipt TEXT, created TEXT NOT NULL)")

                db.execute("CREATE INDEX IF NOT EXISTS submissions_source ON submissions(source)")

    @contextmanager
    def connect(self):
        if self.path is None:
            raise TicketConflict("Enable CODANDY_INTEGRATION_ROOT and restart before creating tickets")
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def submit(self, config, draft):
        packet = review(config, draft)
        if packet["digest"] != draft.digest:
            raise TicketConflict("Draft, target or connection changed. Review the current payload again.")
        key = str(draft.idempotency_key)
        source = source_digest(draft)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            rows = db.execute("SELECT key,digest,state,receipt FROM submissions WHERE key=? OR digest=?",
                              (key, draft.digest)).fetchall()
            if rows:
                if any(row[1] != draft.digest for row in rows):
                    raise TicketConflict("This submission key belongs to a different reviewed draft")
                row = rows[0]
                if row[2] == "created":
                    return json.loads(row[3])
                raise TicketConflict("This submission may already exist in Linear. Check the team before making another ticket.")
            if (draft.source_id and not draft.acknowledge_existing
                    and db.execute("SELECT 1 FROM submissions WHERE source=? LIMIT 1", (source,)).fetchone()):
                raise TicketConflict("This source already has a ticket submission. Review its linked tickets and acknowledge creating another.")
            if db.execute("SELECT count(*) FROM submissions").fetchone()[0] >= 10000:
                raise TicketConflict("Local ticket ledger is full; preserve it before configuring a new storage directory")
            db.execute("INSERT INTO submissions VALUES (?,?,?,?,?,?,?)",
                       (key, draft.digest, str(draft.team_id), source, "uncertain", None, datetime.now(UTC).isoformat()))
        # Reservation commits before network I/O; process crashes and lost responses cannot double-send.
        receipt = linear.create_issue(config, packet["payload"])
        receipt.update({"schema_version": "ticket-link-0.1", "provider": "linear", "digest": draft.digest})
        with self.connect() as db:
            db.execute("UPDATE submissions SET state='created',receipt=? WHERE key=?", (json.dumps(receipt), key))
        return receipt

    def count_source(self, source):
        if not source.source_id:
            return 0
        with self.connect() as db:
            return db.execute("SELECT count(*) FROM submissions WHERE source=?", (source_digest(source),)).fetchone()[0]

    def history(self, source=None):
        with self.connect() as db:
            if source is None:
                rows = db.execute("SELECT state,receipt,created FROM submissions ORDER BY created DESC LIMIT 50").fetchall()
            else:
                rows = db.execute("SELECT state,receipt,created FROM submissions WHERE source=? ORDER BY created DESC LIMIT 50",
                                  (source_digest(source),)).fetchall()
        return {"items": [{"state": row[0], "receipt": json.loads(row[1]) if row[1] else None,
                            "created_at": row[2]} for row in rows]}
