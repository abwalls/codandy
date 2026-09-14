"""Source capture for the report viewer: budgets, exclusions and addressability."""

from app.analyzer import analyze_repository
from app.settings import Settings
from app.sources import collect_sources


def capture(tmp_path, files, **limits):
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        # Written as bytes so fixtures keep exact LF endings on every platform.
        target.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
    settings = Settings(**limits)
    atlas = analyze_repository(tmp_path, "https://github.com/org/repo.git", "main", settings,
                              lambda *_: None)
    return atlas, collect_sources(tmp_path, atlas, settings)


def test_indexed_source_is_captured_verbatim(tmp_path):
    body = "export function run() {\n  return 1;\n}\n"
    atlas, (sources, omitted) = capture(tmp_path, {"index.ts": body, "notes.md": "text\n"})
    assert sources["index.ts"].text == body
    assert sources["index.ts"].lines == 3
    assert sources["index.ts"].truncated is False
    # Inventory-only files stay addressable while the budget allows it.
    assert sources["notes.md"].text == "text\n"
    assert omitted == 0
    # The atlas artifact itself must never carry source bodies.
    assert "return 1;" not in atlas.model_dump_json()


def test_secret_and_binary_paths_are_never_captured(tmp_path):
    _, (sources, _) = capture(tmp_path, {
        "index.ts": "export function run() {}\n",
        ".env": "TOKEN=leak\n",
        "id_rsa": "PRIVATE\n",
        "blob.ts": b"export const x = 1;\x00\x01",
    })
    assert set(sources) == {"index.ts"}


def test_total_budget_prefers_files_carrying_line_evidence(tmp_path):
    # "a-plain.md" sorts first but has no line evidence, so the indexed source is
    # captured before the budget is consumed and the last plain file is dropped.
    _, (sources, omitted) = capture(tmp_path, {
        "a-plain.md": "x" * 4200,
        "b-code.ts": "export function run() {}\n",
        "z-plain.md": "y" * 100,
    }, max_viewer_total_bytes=4096)
    assert set(sources) == {"b-code.ts", "a-plain.md"}
    assert omitted == 1


def test_oversized_files_truncate_on_a_line_boundary(tmp_path):
    body = "".join(f"const line{n} = {n};\n" for n in range(200))
    _, (sources, _) = capture(tmp_path, {"big.ts": body}, max_viewer_file_bytes=1100)
    captured = sources["big.ts"]
    assert captured.truncated is True
    assert captured.text.endswith("\n")
    assert body.startswith(captured.text)
    assert captured.lines == captured.text.count("\n")


def test_only_indexed_repository_paths_become_addressable(tmp_path):
    outside = tmp_path.parent / "codandy-outside-probe.txt"
    outside.write_bytes(b"DO_NOT_READ\n")
    try:
        _, (sources, _) = capture(tmp_path, {"index.ts": "export function run() {}\n"})
    finally:
        outside.unlink()
    assert set(sources) == {"index.ts"}
    assert all(not path.startswith(("..", "/")) and ":" not in path for path in sources)
