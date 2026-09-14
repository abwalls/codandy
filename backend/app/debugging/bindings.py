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

# Bundlers and Sentry's frame rewriting name source files with these schemes.
URL_SCHEMES = {"http", "https", "file", "webpack", "webpack-internal", "app"}


def path_hint(value: str | None) -> tuple[str, bool] | None:
    """A repository-relative path hint, and whether it is anchored at a known root.

    `./` is relative to the bundle or URL root, the same assumption exact URL paths already
    make. `../` and `~/` are relative to an unknown base, so they may only suggest
    candidates by suffix, never an exact path.
    """
    if not value:
        return None
    path = value.replace("\\", "/")
    if "://" in path:
        try:
            parsed = urlsplit(path)
        except ValueError:
            return None
        if parsed.scheme not in URL_SCHEMES:
            return None
        # URL hosts and webpack namespaces are not repository locations.
        path = parsed.path
    elif len(path) >= 2 and path[1] == ":":
        path = path[2:]
    path = path.lstrip("/")
    anchored = True
    while path.startswith(("./", "../", "~/")):
        if not path.startswith("./"):
            anchored = False
        path = path.split("/", 1)[1]
    return (path, anchored) if is_repository_relative(path) else None


def runtime_path(value: str | None) -> str | None:
    """An anchored repository-relative path, or None."""
    hint = path_hint(value)
    return hint[0] if hint and hint[1] else None


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
            hints = [hint for value in (frame.path, frame.abs_path) if (hint := path_hint(value))]
            paths = {path for path, anchored in hints if anchored}
            suffix_only = {path for path, anchored in hints if not anchored}
            mapped = {path[len(prefix) + 1:] for path in paths
                      if prefix and path.startswith(prefix + "/")}
            exact = sorted((paths | mapped) & files.keys())
            method = "path_mapping" if exact and set(exact) & mapped else "exact_path"
            candidates = exact
            if not candidates:
                scored = {}
                for path in paths | suffix_only:
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
            if suffix_only and not paths:
                limitations.append("The runtime path is relative to an unknown base (../ or ~/), so only suffix candidates are offered.")
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
