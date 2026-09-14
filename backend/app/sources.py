"""Source text captured for the report viewer while the workspace still exists.

Read-only text capture. Repository code is never executed, and only paths the
analyzer already indexed as file nodes are eligible, so secret-matched and
excluded paths cannot appear here.
"""

from pathlib import Path

from app.analyzer import SECRET_NAME
from app.models import AtlasDocument, SourceFile
from app.settings import Settings

STRUCTURAL_KINDS = {"file", "directory", "repository"}


def _inside(root: Path, path: str) -> Path | None:
    """Resolve a repository-relative path, rejecting traversal and links."""
    candidate = Path(path)
    if candidate.is_absolute() or candidate.drive or ".." in candidate.parts:
        return None
    target = (root / candidate).resolve()
    if not target.is_relative_to(root.resolve()):
        return None
    if target.is_symlink() or not target.is_file():
        return None
    return target


def collect_sources(root: Path, atlas: AtlasDocument,
                    limits: Settings) -> tuple[dict[str, SourceFile], int]:
    """Capture indexed file text within per-file and total byte budgets."""
    file_paths = {node.path for node in atlas.nodes if node.kind == "file"}
    detailed = {
        evidence.path
        for node in atlas.nodes if node.kind not in STRUCTURAL_KINDS
        for evidence in node.evidence
        if evidence.lines and evidence.path in file_paths
    }
    # Files carrying line evidence are captured first; the rest fill the budget.
    ordered = sorted(detailed) + sorted(file_paths - detailed)
    sources: dict[str, SourceFile] = {}
    used = 0
    omitted = 0
    for path in ordered:
        if SECRET_NAME.search(Path(path).name):
            omitted += 1
            continue
        target = _inside(root, path)
        if target is None:
            omitted += 1
            continue
        if used >= limits.max_viewer_total_bytes:
            omitted += 1
            continue
        try:
            with target.open("rb") as handle:
                data = handle.read(limits.max_viewer_file_bytes + 1)
        except OSError:
            omitted += 1
            continue
        truncated = len(data) > limits.max_viewer_file_bytes
        data = data[:limits.max_viewer_file_bytes]
        if b"\0" in data:
            omitted += 1
            continue
        text = data.decode("utf-8", errors="replace")
        if truncated:
            # Never end on a partial line; the viewer indexes by line number.
            text = text[:text.rfind("\n") + 1] if "\n" in text else ""
            if not text:
                omitted += 1
                continue
        used += len(data)
        sources[path] = SourceFile(path=path, text=text,
                                   lines=text.count("\n") + (0 if text.endswith("\n") else 1),
                                   truncated=truncated)
    return sources, omitted
