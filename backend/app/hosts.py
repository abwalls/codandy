"""Host-name allowlist that blocks DNS rebinding against the local API.

A page on an attacker's domain can re-point that domain at 127.0.0.1. The browser then
treats this API as same-origin, so CORS no longer protects it, but every request still
carries the attacker's name in its Host header.
"""

import re
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

HOST_HEADER = re.compile(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?|\[[0-9A-Fa-f:.]+\](?::[0-9]{1,5})?")


def host_name(value: str) -> str | None:
    """The lower-case host name from a Host header, or None when it is malformed."""
    if not HOST_HEADER.fullmatch(value):
        return None
    try:
        return urlsplit(f"//{value}").hostname
    except ValueError:
        return None


class AllowedHosts:
    def __init__(self, app, hosts: Callable[[], Iterable[str]]):
        self.app = app
        # Read per request, so settings patched by tests apply without rebuilding the app.
        self.hosts = hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            name = host_name(Headers(scope=scope).get("host", ""))
            if name is None or name not in {host.lower() for host in self.hosts()}:
                response = JSONResponse(
                    {"detail": "Use an approved host name such as localhost to reach this API"},
                    status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
