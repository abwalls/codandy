from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.boards import (
    Artifact,
    BoardStore,
    Conflict,
    Draft,
    Edit,
    EvidenceCard,
    Interpretation,
    Plan,
    packet,
    render_plan,
    validate_output,
)
from app.debugging.cases import CaseStore
from app.debugging.stacks import normalize_stack_text
from app.models import AtlasNode, Evidence
from app.routers.board_routes import router


def card():
    return EvidenceCard(kind="case", source_id=str(uuid4()), source_revision="captured", title="Failure", text="Observed stack; root cause unknown", basis="observed stack")


def test_evidence_persistence_revision_deduplication_and_history(tmp_path):
    store = BoardStore(tmp_path)
    board = store.create(Draft())
    evidence = card()
    board = store.evidence(board.id, 1, evidence)
    assert board.revision == 2
    assert store.evidence(board.id, 2, evidence).revision == 2
    with pytest.raises(Conflict):
        store.evidence(board.id, 1, card())
    board = store.update(board.id, Edit(revision=2, notes="Requirement"))
    assert board.evidence_cards[0] == evidence
    restored = BoardStore(tmp_path)
    assert restored.get(board.id).evidence_cards == [evidence]
    plan = Plan(title="Fix", objective="Investigate", in_scope=[], out_of_scope=[], decisions=[],
                tasks=[{"id": "one", "title": "Verify", "description": "Review stack", "depends_on": [], "acceptance_criteria": ["Reproduced"], "verification": ["Run fixture"], "proposed_paths": []}], risks=[], open_questions=[])
    artifact = Artifact(revision=3,stage="plan",digest="x",model="test",plan=plan,evidence_cards=[evidence])
    restored.add_artifact(board.id, artifact)
    updated = restored.evidence(board.id,3,remove=evidence.id)
    assert updated.revision == 4 and not updated.evidence_cards
    output = render_plan(updated, updated.artifacts[0])
    assert "STALE" in output and str(evidence.id) in output and evidence.text in output


def test_evidence_citations_must_be_in_exact_reviewed_packet():
    store=BoardStore(None)
    board=store.create(Draft())
    evidence=card()
    board=store.evidence(board.id,1,evidence)
    review=packet(board,"interpret")
    result=Interpretation(summary="Observed failure",findings=[{"text": "Failure","element_ids": [],"evidence_ids": [str(evidence.id)],"basis": "captured_evidence"}],questions=[],assumptions=[])
    assert validate_output(result,review)==result
    result.findings[0].evidence_ids=[str(uuid4())]
    with pytest.raises(ValueError):
        validate_output(result,review)
    result.findings[0].evidence_ids=[]
    with pytest.raises(ValueError):
        validate_output(result,review)
    removed=store.evidence(board.id,2,remove=evidence.id)
    assert packet(removed,"interpret")["digest"] != review["digest"]


def test_evidence_limit_and_forged_draft_rejected():
    store=BoardStore(None)
    board=store.create(Draft())
    for _ in range(10):
        board=store.evidence(board.id,board.revision,card())
    with pytest.raises(ValueError):
        store.evidence(board.id,board.revision,card())
    with pytest.raises(ValueError):
        Draft.model_validate({"evidence_cards":[card().model_dump(mode="json")]})


def test_pin_api_resolves_scrubbed_local_evidence_and_keeps_copies_after_source_deleted():
    app=FastAPI();app.include_router(router,prefix="/api")
    app.state.boards=BoardStore(None)
    app.state.investigations=CaseStore(None)
    observation=app.state.investigations.remember(normalize_stack_text("Error: password=hunter2\n at fail (/app/main.js:3:1)"))
    case=app.state.investigations.save(observation.id)
    snapshot=uuid4()
    atlas=SimpleNamespace(repository={"name":"sample","commit":"a"*40},nodes=[AtlasNode(id="node1",kind="function",label="handle",detail="token=secretvalue",path="app.py",confidence=100,evidence=[Evidence(path="app.py",lines="1-3",reason="declared")])])
    app.state.jobs=SimpleNamespace(result=lambda value:atlas if value==snapshot else None)
    board=app.state.boards.create(Draft());path=f"/api/boards/{board.id}"
    headers={"X-Codandy-Local":"1"}
    with TestClient(app,base_url="http://localhost",client=("127.0.0.1",1234)) as client:
        assert client.get(path+"/evidence-options?kind=case").status_code==403
        values=client.get(path+"/evidence-options?kind=case",headers=headers).json()
        assert values["items"][0]["id"]==str(case.id)
        assert client.post(path+"/evidence",headers=headers,json={"revision": 1,"kind": "case","source_id": str(uuid4())}).status_code==404
        response=client.post(path+"/evidence",headers=headers,json={"revision": 1,"kind": "case","source_id": str(case.id)})
        assert response.status_code==200 and "hunter2" not in response.text
        captured=response.json()["evidence_cards"][0]
        app.state.investigations.delete(case.id)
        assert client.get(path+"/review",headers=headers).json()["packet"]["evidence_cards"][0]==captured
        payload={"revision": 2,"kind": "source","source_id": "node1","snapshot_id": str(uuid4())}
        assert client.post(path+"/evidence",headers=headers,json=payload).status_code==404
        payload["snapshot_id"]=str(snapshot)
        result=client.post(path+"/evidence",headers=headers,json=payload)
        assert result.status_code==200 and "secretvalue" not in result.text
        source=result.json()["evidence_cards"][-1]
        assert "app.py:1-3" in source["text"] and source["snapshot_id"]==str(snapshot)
        assert client.delete(path+f"/evidence/{source['id']}?revision=2",headers=headers).status_code==409
        assert client.delete(path+f"/evidence/{source['id']}?revision=3",headers=headers).status_code==200


def test_ai_finding_schema_requires_new_citations_but_old_artifacts_still_load():
    schema = Interpretation.model_json_schema()["$defs"]["Finding"]
    assert set(schema["required"]) == set(schema["properties"])
    old = Interpretation(summary="Old artifact", findings=[{"text":"Guess", "element_ids":[], "basis":"assumed"}], questions=[], assumptions=[])
    assert old.findings[0].evidence_ids == []
