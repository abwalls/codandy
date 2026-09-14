"""Explicit, bounded Sentry Cloud reads. No redirects, proxies, or payload URLs."""

import re
import ssl
import time
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener

from app.debugging.models import DebuggingLimits
from app.debugging.payload import NormalizationError
from app.debugging.sentry_event import normalize_sentry_event_bytes

HOSTS = {"sentry.io", "us.sentry.io", "de.sentry.io"}


class SentryError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_event(config, issue: str, event: str):
    if config.sentry_host not in HOSTS:
        raise SentryError("Unsupported Sentry Cloud host")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", config.sentry_organization):
        raise SentryError("Configure a valid Sentry organization slug on the backend")
    if not re.fullmatch(r"[0-9]{1,32}", issue):
        raise SentryError("Use the numeric Sentry issue ID")
    if not re.fullmatch(r"(?:latest|oldest|recommended|[a-fA-F0-9]{32})", event):
        raise SentryError("Use latest, oldest, recommended, or a 32-character event ID")
    token = config.sentry_token.get_secret_value()
    if not token:
        raise SentryError("Configure CODANDY_SENTRY_TOKEN on the local backend first")
    if not re.fullmatch(r"[A-Za-z0-9_./+=-]{1,4096}", token):
        raise SentryError("The configured Sentry token has an invalid format")
    url = (f"https://{config.sentry_host}/api/0/organizations/"
           f"{config.sentry_organization}/issues/{issue}/events/{event}/")
    request = Request(url, headers={"Authorization": f"Bearer {token}",
                                   "Accept": "application/json", "Accept-Encoding": "identity"})
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()),
                         NoRedirect())
    limits = DebuggingLimits()
    deadline = time.monotonic() + 20
    try:
        with opener.open(request, timeout=5) as response:
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
    try:
        observation = normalize_sentry_event_bytes(bytes(data), limits, issue_id=issue,
                                                   fetched_at=datetime.now(UTC))
    except NormalizationError:
        raise SentryError("Sentry returned an unsupported or oversized event response") from None
    if event not in {"latest", "oldest", "recommended"} and observation.source.event_id != event:
        raise SentryError("Sentry returned a different event than requested")
    return observation
