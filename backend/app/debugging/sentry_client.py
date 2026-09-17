"""Explicit, bounded Sentry Cloud reads. No redirects, proxies, or payload URLs."""

import re
import ssl
import time
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from app.debugging.models import DebuggingLimits
from app.debugging.payload import NormalizationError, load_json
from app.debugging.redaction import Redactor
from app.debugging.sentry_event import normalize_sentry_event_bytes

HOSTS = {"sentry.io", "us.sentry.io", "de.sentry.io"}


class SentryError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _fetch(config, path):
    if config.sentry_host not in HOSTS:
        raise SentryError("Unsupported Sentry Cloud host")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", config.sentry_organization):
        raise SentryError("Configure a valid Sentry organization slug on the backend")
    token = config.sentry_token.get_secret_value()
    if not token:
        raise SentryError("Configure CODANDY_SENTRY_TOKEN on the local backend first")
    if not re.fullmatch(r"[A-Za-z0-9_./+=-]{1,4096}", token):
        raise SentryError("The configured Sentry token has an invalid format")
    url = (f"https://{config.sentry_host}/api/0/organizations/"
           f"{config.sentry_organization}/{path}")
    request = Request(url, headers={"Authorization": f"Bearer {token}",
                                   "Accept": "application/json", "Accept-Encoding": "identity"})
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()),
                         NoRedirect())
    limits = DebuggingLimits()
    deadline = time.monotonic() + 20
    try:
        with opener.open(request, timeout=5) as response:
            link = getattr(response, "headers", {}).get("Link", "")[:8192]
            data = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise SentryError("Sentry retrieval exceeded its time budget; try again")
                chunk = response.read1(min(65536, limits.max_payload_bytes + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > limits.max_payload_bytes:
                    raise SentryError("Sentry event exceeds the 2 MiB import budget")
    except HTTPError as exc:
        code = exc.code
        exc.close()
        message = {401: "Sentry rejected the token", 403: "Sentry denied access; check event:read and organization access",
                   404: "Sentry issue or event was not found", 429: "Sentry rate limit reached; wait before retrying"}.get(
                       code, "Sentry returned an unsuccessful response; redirects are not followed")
        raise SentryError(message) from None
    except (URLError, TimeoutError, OSError):
        raise SentryError("Could not reach Sentry within the connection timeout") from None
    return bytes(data), link


def fetch_event(config, issue: str, event: str):
    if not re.fullmatch(r"[0-9]{1,32}", issue):
        raise SentryError("Use the numeric Sentry issue ID")
    if not re.fullmatch(r"(?:latest|oldest|recommended|[a-fA-F0-9]{32})", event):
        raise SentryError("Use latest, oldest, recommended, or a 32-character event ID")
    data, _link = _fetch(config, f"issues/{issue}/events/{event}/")
    try:
        observation = normalize_sentry_event_bytes(data, DebuggingLimits(), issue_id=issue,
                                                   fetched_at=datetime.now(UTC))
    except NormalizationError:
        raise SentryError("Sentry returned an unsupported or oversized event response") from None
    if event not in {"latest", "oldest", "recommended"} and observation.source.event_id != event:
        raise SentryError("Sentry returned a different event than requested")
    return observation


CURSOR = r"[0-9]{1,20}:[0-9]{1,20}:[01]"


def browse(config, kind, *, project="", query="", cursor=""):
    if kind not in {"projects", "issues"}:
        raise SentryError("Unsupported Sentry listing")
    if cursor and not re.fullmatch(CURSOR, cursor):
        raise SentryError("Unsupported pagination cursor")
    if len(query) > 300 or any(ord(char) < 32 for char in query):
        raise SentryError("Use a search query of at most 300 characters without control characters")
    params = {"query": query, "per_page" if kind == "projects" else "limit": "50"}
    if kind == "issues":
        if not re.fullmatch(r"[0-9]{1,32}", project):
            raise SentryError("Select a numeric Sentry project ID")
        params.update({"project": project, "shortIdLookup": "0", "sort": "date"})
    if cursor:
        params["cursor"] = cursor
    data, links = _fetch(config, f"{kind}/?{urlencode(params)}")
    try:
        rows = load_json(data, DebuggingLimits())
        if not isinstance(rows, list) or len(rows) > 50:
            raise ValueError()
        redactor = Redactor()
        credential = config.sentry_token.get_secret_value()
        def text(value, length):
            if value is None:
                return ""
            if not isinstance(value, str):
                raise TypeError()
            return redactor.text(value.replace(credential, "[redacted:credential]"), kind)[:length]
        items = []
        for row in rows:
            identifier = row["id"]
            if not isinstance(identifier, str) or not re.fullmatch(r"[0-9]{1,32}", identifier):
                raise ValueError()
            if kind == "projects":
                items.append({"id": identifier, "name": text(row.get("name"), 200), "slug": text(row.get("slug"), 100)})
            else:
                if row["project"]["id"] != project:
                    raise ValueError()
                items.append({"id": identifier, "title": text(row.get("title"), 500),
                              "culprit": text(row.get("culprit"), 300), "status": text(row.get("status"), 60)})
    except (ValueError, KeyError, TypeError):
        raise SentryError("Sentry returned an unsupported listing; no provider body was retained") from None
    next_cursor = None
    notes = ["One page, up to 50 results. Only displayed fields are retained in this tab; raw responses are not saved."]
    for part in links.split(","):
        if 'rel="next"' not in part or 'results="true"' not in part:
            continue
        match = re.search(r'cursor="(' + CURSOR + r')"', part)
        if match:
            next_cursor = match[1]
        else:
            notes.append("More results were reported, but the pagination cursor is unsupported.")
    # Link URLs are deliberately ignored; every later request is rebuilt for the fixed host.
    return {"items": items, "next_cursor": next_cursor, "notes": notes}
