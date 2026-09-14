"""Conservative path candidates against an existing static snapshot, never the filesystem."""

from pathlib import PurePosixPath
from urllib.parse import urlsplit
from uuid import UUID

from app.debugging.models import (
    BindingCandidate,
    Observation,
    SourceBinding,
    is_repository_relative,
)
from app.models import AtlasDocument


def runtime_path(value: str | None) -> str | None:
    if not value:
        return None
    path = value.replace("\\", "/")
    if "://" in path:
        try:
            parsed = urlsplit(path)
            if parsed.scheme not in {"http", "https", "webpack", "file"}:
                return None
            path = parsed.path
        except ValueError:
            return None
    elif len(path) >= 2 and path[1] == ":":
        path = path[2:]
    path = path.lstrip("/")
    return path if is_repository_relative(path) else None


def bind_observation(observation: Observation, atlas: AtlasDocument, snapshot_id: UUID,
                     runtime_commit: str | None = None, path_prefix: str = "") -> list[SourceBinding]:
    files = {node.path: node for node in atlas.nodes
             if node.kind == "file" and is_repository_relative(node.path)}
    by_name: dict[str, list[str]] = {}
    for path in files:
        by_name.setdefault(PurePosixPath(path).name, []).append(path)
    prefix = runtime_path(path_prefix)
    snapshot_commit = atlas.repository.get("commit")
    revision = "mismatch" if runtime_commit and snapshot_commit and runtime_commit.lower() != snapshot_commit.lower() else "unknown"
    results = []
    for exception in observation.exceptions:
        for frame in exception.frames:
            paths = {path for value in (frame.path, frame.abs_path) if (path := runtime_path(value))}
            mapped = {path[len(prefix) + 1:] for path in paths
                      if prefix and path.startswith(prefix + "/")}
            exact = sorted((paths | mapped) & files.keys())
            method = "path_mapping" if exact and set(exact) & mapped else "exact_path"
            candidates = exact
            if not candidates:
                scored = {}
                for path in paths:
                    parts = path.split("/")
                    for candidate in by_name.get(parts[-1], []):
                        score = 0
                        for a, b in zip(reversed(parts), reversed(candidate.split("/"))):
                            if a != b:
                                break
                            score += 1
                        scored[candidate] = max(score, scored.get(candidate, 0))
                best = max(scored.values(), default=0)
                candidates = sorted(path for path, score in scored.items() if score == best)
                method = "path_suffix" if best > 1 else "basename" if best else "none"
            limitations = ["Path matches are candidates; runtime source revision is not independently verified."]
            if runtime_commit:
                limitations.append("Runtime commit was supplied by the user, not verified from provider evidence.")
            if revision == "mismatch":
                limitations.append("Reported runtime commit differs from the selected snapshot; line numbers may be wrong.")
            if len(candidates) > 20:
                # Do not silently promote one candidate after truncating competitors.
                limitations.append(f"{len(candidates)} competing paths exceed the candidate budget; refine the path mapping.")
                candidates, method = [], "none"
            status = "unmapped" if not candidates else "candidate" if len(candidates) == 1 else "ambiguous"
            results.append(SourceBinding(observation_id=observation.id,
                exception_index=exception.index, frame_index=frame.index, snapshot_id=snapshot_id,
                status=status, method=method, revision=revision,
                candidates=[BindingCandidate(path=path, line=frame.line, node_ids=[files[path].id])
                            for path in candidates], limitations=limitations))
    return results
