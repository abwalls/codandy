"""Bounded manifest/lock metadata. Never execute dependency tooling or retain URLs."""

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from app.models import AtlasDocument, Evidence


def safe_version(value) -> str:
    if not isinstance(value, str) or len(value) > 160:
        return ""
    value = value.strip()
    # Numeric version constraints only, not URLs, aliases, environment expressions or tags.
    if not re.fullmatch(r"[v\d<>=~^*\[\](][0-9A-Za-z.*+<>=~^|,\[\]() -]*", value):
        return ""
    if not re.search(r"\d", value) or any(word in value.lower() for word in ("http", "token", "password", "secret")):
        return ""
    return value


def exact_version(value: str) -> str:
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    elif value.startswith("=="):
        value = value[2:]
    match = re.fullmatch(r"(v?\d+(?:\.\d+){0,3}(?:[-+][0-9A-Za-z.-]+)?)", value)
    return match.group(1) if match else ""


def read_small(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        return b""
    return path.read_bytes()


def go_requirements(text: str) -> list[tuple[str, str]]:
    """Read only require directives, never exclude/replace block entries."""
    entries = []
    block = ""
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if line == ")":
            block = ""
            continue
        opening = re.fullmatch(r"(\w+)\s*\(", line)
        if opening:
            block = opening[1]
            continue
        if block == "require":
            value = line
        elif not block and line.startswith("require "):
            value = line[len("require "):].strip()
        else:
            continue
        match = re.fullmatch(r"([A-Za-z0-9][\w.~/-]{0,199})\s+(v[\w.+-]{1,100})", value)
        if match:
            entries.append((match[1], match[2]))
    return entries


def enrich_central_nuget(root: Path, atlas: AtlasDocument, limit: int):
    """Show central declarations as candidates, without evaluating MSBuild selection."""
    indexed = {node.path for node in atlas.nodes if node.kind == "file"}
    cache = {}
    for node in atlas.nodes:
        if node.kind != "dependency" or node.attributes.get("ecosystem") != "NuGet":
            continue
        directory = (root / node.path).parent
        while True:
            central_path = (directory / "Directory.Packages.props").relative_to(root).as_posix()
            if central_path in indexed:
                break
            if directory == root:
                central_path = ""
                break
            directory = directory.parent
        if not central_path:
            continue
        if central_path not in cache:
            versions = {}
            try:
                data = read_small(root / central_path, limit)
                if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", data, re.IGNORECASE):
                    raise ValueError("XML declarations unsupported")
                for entry in ET.fromstring(data).iter():
                    if entry.tag.rsplit("}", 1)[-1] != "PackageVersion":
                        continue
                    name = entry.attrib.get("Include") or entry.attrib.get("Update", "")
                    value = entry.attrib.get("Version") or next((child.text for child in entry
                        if child.tag.rsplit("}", 1)[-1] == "Version"), "")
                    version = safe_version(value)
                    if version:
                        versions.setdefault(name.lower(), set()).add(version)
            except (ValueError, TypeError, AttributeError, OSError, ET.ParseError):
                versions = {}
                atlas.limitations.append(f"Central NuGet declarations unavailable for {central_path}; format invalid or unsupported.")
            cache[central_path] = versions
        candidates = sorted(cache[central_path].get(node.label.lower(), set()))
        if candidates:
            node.attributes.update({"central_version_candidates": " | ".join(candidates[:8]),
                                    "central_version_file": central_path,
                                    "central_candidates_truncated": len(candidates) > 8})
            node.evidence.append(Evidence(path=central_path,
                reason="Same-name PackageVersion candidates in nearest central file; conditions, imports and overrides not evaluated"))


def enrich_dependencies(root: Path, atlas: AtlasDocument, limit: int):
    grouped = {}
    indexed = {node.path for node in atlas.nodes if node.kind == "file"}
    for node in atlas.nodes:
        if node.kind == "dependency":
            grouped.setdefault(node.path, []).append(node)
    for path, nodes in grouped.items():
        manifest = root / path
        try:
            data = read_small(manifest, limit)
            versions, locks = {}, {}
            conflicts = set()

            def record(key, value, versions=versions, conflicts=conflicts):
                if key in conflicts or key in versions and versions[key] != value:
                    conflicts.add(key)
                    versions[key] = ""
                else:
                    versions[key] = value
            lock_path = ""
            version_note = ""
            if manifest.name == "package.json":
                ecosystem = "npm"
                document = json.loads(data)
                for group in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                    entries = document.get(group, {})
                    if isinstance(entries, dict):
                        for name, value in entries.items():
                            record((group, name), safe_version(value))
                lock_path = (manifest.parent / "package-lock.json").relative_to(root).as_posix()
                if lock_path in indexed:
                    lock = json.loads(read_small(root / lock_path, limit) or b"{}")
                    packages = lock.get("packages", {})
                    for node in nodes:
                        entry = packages.get(f"node_modules/{node.label}", {})
                        if not entry:
                            entry = lock.get("dependencies", {}).get(node.label, {})
                        locks[node.label] = exact_version(safe_version(entry.get("version")))
            elif manifest.suffix in {".csproj", ".fsproj", ".vbproj"}:
                ecosystem = "NuGet"
                if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", data, re.IGNORECASE):
                    continue
                for entry in ET.fromstring(data).iter():
                    if entry.tag.rsplit("}", 1)[-1] == "PackageReference":
                        value = entry.attrib.get("Version", "")
                        if not value:
                            value = next((child.text for child in entry
                                          if child.tag.rsplit("}", 1)[-1] == "Version"), "")
                        record(entry.attrib.get("Include", ""), safe_version(value))
                lock_path = (manifest.parent / "packages.lock.json").relative_to(root).as_posix()
                if lock_path in indexed:
                    lock = json.loads(read_small(root / lock_path, limit) or b"{}")
                    for node in nodes:
                        candidates = {exact_version(safe_version(value.get("resolved")))
                                      for framework in lock.get("dependencies", {}).values()
                                      for name, value in framework.items()
                                      if name.lower() == node.label.lower()}
                        if len(candidates) == 1 and "" not in candidates:
                            locks[node.label] = candidates.pop()
            elif manifest.name in {"pyproject.toml", "requirements.txt"}:
                ecosystem = "PyPI"
                entries = []
                if manifest.name == "requirements.txt":
                    entries = data.decode("utf-8").splitlines()
                else:
                    document = tomllib.loads(data.decode("utf-8"))
                    project = document.get("project", {})
                    entries.extend(project.get("dependencies", []))
                    for values in project.get("optional-dependencies", {}).values():
                        entries.extend(values)
                    for name, value in document.get("tool", {}).get("poetry", {}).get("dependencies", {}).items():
                        record(name.lower(), safe_version(value if isinstance(value, str) else value.get("version")))
                for entry in entries:
                    if not isinstance(entry, str):
                        continue
                    match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*([^;#]*)", entry)
                    if match:
                        record(match[1].lower(), safe_version(match[2]))
            elif manifest.name == "go.mod":
                ecosystem = "Go"
                text = data.decode("utf-8")
                for name, version in go_requirements(text):
                    record(name, safe_version(version))
                if re.search(r"^\s*(?:replace|exclude)\b", text, re.MULTILINE):
                    version_note = "Go replacement/exclusion directives are present; selected package versions are not resolved."
            else:
                continue
            for node in nodes:
                key = (node.attributes.get("group"), node.label) if ecosystem == "npm" else node.label.lower() if ecosystem == "PyPI" else node.label
                declared = versions.get(key, "")
                node.attributes.update({"ecosystem": ecosystem, "declared_version": declared,
                                        "version_basis": "unknown"})
                locked = locks.get(node.label)
                exact = exact_version(declared)
                if ecosystem == "NuGet" and not (declared.startswith("[") and declared.endswith("]")):
                    exact = ""
                if version_note:
                    exact = ""
                    node.attributes["version_note"] = version_note
                if locked:
                    node.attributes.update({"checked_version": locked, "version_basis": "lockfile", "lockfile": lock_path})
                    node.evidence.append(Evidence(path=lock_path, reason="Resolved version recorded in lockfile; runtime installation not verified"))
                elif exact and (ecosystem != "npm" or re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", exact)):
                    node.attributes.update({"checked_version": exact, "version_basis": "declared"})
        except (ValueError, TypeError, AttributeError, OSError, ET.ParseError):
            atlas.limitations.append(f"Dependency version metadata unavailable for {path}; manifest/lock format unsupported or invalid.")
