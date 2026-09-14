from uuid import uuid4

import pytest

from app.debugging.bindings import bind_observation, runtime_path
from app.debugging.cases import CaseStore
from app.debugging.stacks import normalize_stack_text
from app.models import AtlasDocument, AtlasNode


def atlas(*paths):
    return AtlasDocument(repository={"commit": "a" * 40, "url": "https://github.com/example/app"},
        technologies=[], nodes=[AtlasNode(id=str(i), kind="file", label=path,
        path=path, detail="", confidence=100) for i, path in enumerate(paths)],
        relationships=[], counts={}, limitations=[])


def observed(path):
    return normalize_stack_text(f"Error: failed\n at fail ({path}:4:2)")


def test_exact_path_is_only_a_candidate_without_verified_revision():
    snapshot = uuid4()
    binding = bind_observation(observed("src/app.js"), atlas("src/app.js"), snapshot)[0]
    assert binding.status == "candidate"
    assert binding.method == "exact_path"
    assert binding.revision == "unknown"
    assert binding.candidates[0].node_ids == ["0"]
    assert binding.snapshot_id == snapshot


def test_suffix_and_duplicate_basenames_preserve_ambiguity():
    source = atlas("frontend/app.js", "backend/app.js")
    binding = bind_observation(observed("/srv/app.js"), source, uuid4())[0]
    assert binding.status == "ambiguous"
    assert len(binding.candidates) == 2
    suffix = bind_observation(observed("/srv/frontend/app.js"), source, uuid4())[0]
    assert suffix.candidates[0].path == "frontend/app.js"
    assert suffix.method == "path_suffix"


def test_mapping_and_reported_revision_never_upgrade_to_verified():
    source = atlas("src/app.js")
    binding = bind_observation(observed("/srv/project/src/app.js"), source, uuid4(), "a" * 40, "/srv/project")[0]
    assert binding.method == "path_mapping"
    assert binding.revision == "unknown"
    mismatch = bind_observation(observed("src/app.js"), source, uuid4(), "b" * 40)[0]
    assert mismatch.revision == "mismatch"
    assert mismatch.status == "candidate"


@pytest.mark.parametrize("path", ["../private.txt", "a/../../secret", "https://example.com/a/../secret", "data:text/plain,secret", "abc\x00/file"])
def test_unsafe_runtime_paths_never_bind(path):
    assert runtime_path(path) is None


def test_urls_are_path_hints_only_and_missing_files_stay_unmapped():
    source = atlas("src/app.js")
    binding = bind_observation(observed("https://127.0.0.1/src/app.js?token=private"), source, uuid4())[0]
    assert binding.candidates[0].path == "src/app.js"
    assert bind_observation(observed("missing.js"), source, uuid4())[0].status == "unmapped"


def test_excessive_ambiguity_is_not_silently_truncated_to_one_match():
    source = atlas(*(f"dir{i}/app.js" for i in range(21)))
    binding = bind_observation(observed("app.js"), source, uuid4())[0]
    assert binding.status == "unmapped"
    assert any("21 competing" in note for note in binding.limitations)


def test_bindings_survive_restart_without_mutating_observation(tmp_path):
    store = CaseStore(tmp_path)
    saved = store.save(store.remember(observed("src/app.js")).id)
    snapshot = uuid4()
    bound = store.bind(saved.id, atlas("src/app.js"), snapshot, "b" * 40, "")
    restored = CaseStore(tmp_path).get(saved.id)
    assert restored == bound
    assert restored.observation == saved.observation
    assert restored.bindings[0].snapshot_id == snapshot
    assert restored.bindings[0].revision == "mismatch"
