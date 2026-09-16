"""Fixed-host Linear operations. Never retry a mutation automatically."""
import json
import re
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from app.debugging.models import DebuggingLimits
from app.debugging.payload import load_json
from app.debugging.redaction import Redactor
from app.debugging.sentry_client import NoRedirect


class ProviderError(ValueError):
    pass


def key(config):
    value = config.linear_api_key.get_secret_value()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,4096}", value):
        raise ProviderError("Configure a valid CODANDY_LINEAR_API_KEY on the backend and restart")
    return value


def query(config, document, variables=None):
    request = Request("https://api.linear.app/graphql", method="POST",
                      data=json.dumps({"query": document, "variables": variables or {}}).encode(),
                      headers={"Authorization": key(config), "Content-Type": "application/json",
                               "Accept": "application/json", "Accept-Encoding": "identity"})
    opener = build_opener(ProxyHandler({}), HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
    deadline = time.monotonic() + 20
    try:
        with opener.open(request, timeout=5) as response:
            data = bytearray()
            while True:
                if time.monotonic() > deadline:
                    raise ProviderError("Linear response exceeded the time budget")
                chunk = response.read1(min(65536, 2_097_153 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > 2_097_152:
                    raise ProviderError("Linear response exceeds 2 MiB")
    except HTTPError as exc:
        code = exc.code
        exc.close()
        raise ProviderError({401: "Linear rejected the API key", 403: "Linear denied access",
                             429: "Linear rate limit reached; wait before retrying"}.get(
                                 code, "Linear request failed; redirects are not followed")) from None
    except (URLError, TimeoutError, OSError):
        raise ProviderError("Linear connection failed or timed out") from None
    try:
        result = load_json(bytes(data), DebuggingLimits())
        if not isinstance(result, dict) or result.get("errors") or not isinstance(result.get("data"), dict):
            raise ValueError()
        return result["data"]
    except ValueError:
        raise ProviderError("Linear returned an unsuccessful or unsupported response") from None


def test_connection(config):
    result = query(config, "query { viewer { id } }")
    if not isinstance(result.get("viewer"), dict) or not result["viewer"].get("id"):
        raise ProviderError("Linear did not confirm the connection")


def teams(config):
    result = query(config, "query { teams(first: 50) { nodes { id name } pageInfo { hasNextPage } } }")
    try:
        from uuid import UUID
        connection = result["teams"]
        rows = connection["nodes"]
        if not isinstance(rows, list) or len(rows) > 50:
            raise ValueError()
        redactor = Redactor()
        items = [{"id": str(UUID(row["id"])), "name": redactor.text(row["name"], "team")[:200]}
                 for row in rows if isinstance(row["name"], str)]
        return {"items": items, "has_more": bool(connection["pageInfo"]["hasNextPage"])}
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ProviderError("Linear returned unsupported team information") from None


def create_issue(config, payload):
    result = query(config, "mutation($input: IssueCreateInput!) { issueCreate(input: $input) { success issue { id identifier } } }",
                   {"input": payload})
    try:
        from uuid import UUID
        created = result["issueCreate"]
        identifier = created["issue"]["identifier"]
        if created["success"] is not True or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}-[0-9]{1,20}", identifier):
            raise ValueError()
        return {"external_id": str(UUID(created["issue"]["id"])), "external_key": identifier,
                "url": f"https://linear.app/issue/{identifier}"}
    except (KeyError, TypeError, ValueError):
        raise ProviderError("Linear did not return a confirmed issue; check your team before trying again") from None
