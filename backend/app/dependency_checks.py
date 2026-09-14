"""Explicit public metadata lookups; fixed registries, no package downloads or execution."""

import json
import re
import threading
from datetime import UTC, datetime
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from app.dependency_versions import exact_version, safe_version
from app.models import AtlasNode

slots = threading.BoundedSemaphore(4)
ALLOWED_HOSTS = {"registry.npmjs.org", "pypi.org", "api.nuget.org", "proxy.golang.org", "api.osv.dev"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def public_json(url: str, body=None):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise ValueError("Unapproved metadata endpoint")
    request = Request(url, data=json.dumps(body).encode() if body is not None else None,
                      headers={"Accept": "application/json", "Content-Type": "application/json",
                               "User-Agent": "CodeAtlas/0.1 dependency-metadata"})
    with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=8) as response:
        payload = response.read(4 * 1024 * 1024 + 1)
        if len(payload) > 4 * 1024 * 1024:
            raise ValueError("Metadata response exceeds limit")
        return json.loads(payload)


def registry_version(ecosystem: str, name: str):
    encoded = quote(name, safe="")
    if ecosystem == "npm":
        return public_json(f"https://registry.npmjs.org/{encoded}/latest").get("version"), "npm latest tag"
    if ecosystem == "PyPI":
        return public_json(f"https://pypi.org/pypi/{encoded}/json").get("info", {}).get("version"), "PyPI latest release"
    if ecosystem == "Go":
        escaped = "".join("!" + char.lower() if char.isupper() else char for char in name)
        return public_json(f"https://proxy.golang.org/{quote(escaped, safe='/!')}/@latest").get("Version"), "Go proxy latest"
    if ecosystem == "NuGet":
        index = public_json("https://api.nuget.org/v3/index.json")
        base = next(entry["@id"] for entry in index["resources"] if entry.get("@type") == "PackageBaseAddress/3.0.0")
        versions = public_json(f"{base.rstrip('/')}/{encoded.lower()}/index.json").get("versions", [])
        stable = [version for version in versions if isinstance(version, str) and re.fullmatch(r"\d+(?:\.\d+){1,3}", version)]
        return max(stable, key=lambda value: tuple(map(int, value.split(".")))) if stable else None, "NuGet highest stable published version (may include unlisted releases)"
    raise ValueError("Unsupported ecosystem")


def check_dependency(node: AtlasNode) -> dict:
    ecosystem = node.attributes.get("ecosystem")
    name = node.label
    if ecosystem not in {"npm", "NuGet", "PyPI", "Go"} or not re.fullmatch(r"(?:@[A-Za-z0-9_.-]+/)?[A-Za-z0-9][A-Za-z0-9_.~/!-]{0,199}", name) or any(part in {".", ".."} for part in name.split("/")):
        raise ValueError("Package metadata is unsupported; reanalyze this repository")
    version = exact_version(safe_version(node.attributes.get("checked_version", "")))
    result = {"node_id": node.id, "checked_at": datetime.now(UTC).isoformat(),
              "version": version or None, "version_basis": node.attributes.get("version_basis", "unknown"),
              "latest_version": None, "registry_status": "unavailable", "registry_basis": "",
              "update_status": "unknown", "vulnerability_status": "unknown_version" if not version else "unavailable",
              "advisories": [], "advisories_truncated": False}
    try:
        latest, basis = registry_version(ecosystem, name)
        latest = exact_version(safe_version(latest))
        if latest:
            result.update(latest_version=latest, registry_status="checked", registry_basis=basis)
            numeric = lambda value: tuple(int(part) for part in value.removeprefix("v").split("."))
            if latest == version:
                result["update_status"] = "same_version"
            elif version and all(re.fullmatch(r"v?\d+(?:\.\d+){0,3}", value) for value in (version, latest)):
                old, new = numeric(version), numeric(latest)
                width = max(len(old), len(new))
                result["update_status"] = "newer_available" if new + (0,) * (width - len(new)) > old + (0,) * (width - len(old)) else "not_newer"
    except Exception:  # noqa: BLE001 - network/provider failures are explicit, never a clean result
        result["registry_status"] = "unavailable"
    if version:
        try:
            response = public_json("https://api.osv.dev/v1/query", {"package": {"name": name, "ecosystem": ecosystem}, "version": version})
            advisories = response.get("vulns", [])
            if not isinstance(advisories, list):
                raise TypeError("Invalid advisory response")
            for advisory in advisories:
                if advisory.get("withdrawn"):
                    continue
                advisory_id = advisory.get("id", "")
                if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,150}", advisory_id):
                    raise ValueError("Invalid advisory identity")
                result["advisories"].append({"id": advisory_id,
                    "summary": str(advisory.get("summary") or "Reported affected package version")[:1200],
                    "url": "https://osv.dev/vulnerability/" + quote(advisory_id, safe="")})
            result["advisories_truncated"] = len(result["advisories"]) > 30 or bool(response.get("next_page_token"))
            result["advisories"] = result["advisories"][:30]
            result["vulnerability_status"] = "reported" if result["advisories"] else "incomplete" if result["advisories_truncated"] else "no_matches"
        except Exception:  # noqa: BLE001
            result["advisories"] = []
            result["vulnerability_status"] = "unavailable"
    return result
