import base64
import json
import struct
import threading
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.board_images import PREFIX, attach_image, image_bytes, visual_scene
from app.boards import BoardStore, Draft, Interpretation, Scene, packet, validate_output
from app.codex_bridge import CodexBridge
from app.routers.board_routes import router


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(pixel=b"\xff\x00\x00\xff", width=1, extra=b"", pixels=None):
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, 1, 8, 6, 0, 0, 0)) + extra +
            chunk(b"IDAT", zlib.compress(b"\x00" + pixel if pixels is None else pixels)) + chunk(b"IEND", b""))


def encoded(raw):
    return PREFIX + base64.b64encode(raw).decode()


def draft():
    return Draft(scene=Scene(elements=[{"id": "stroke", "type": "freedraw", "points": [[0, 0], [20, 20]]},
                                      {"id": "label", "type": "text", "text": "token=secretvalue", "originalText": "token=secretvalue"}]))


def test_png_strips_metadata_and_binds_visual_digest():
    raw = png(extra=chunk(b"tEXt", b"private embedded scene"))
    normalized, width, height = image_bytes(encoded(raw))
    assert (width, height) == (1, 1)
    assert b"private" not in normalized
    board = BoardStore(None).create(draft())
    review = packet(board, "interpret")
    original = review["digest"]
    attach_image(review, encoded(raw))
    assert review["digest"] != original
    assert "not interpreted visually" not in review["text"]
    assert review["image_info"]["width"] == 1
    second = packet(board, "interpret")
    attach_image(second, encoded(png(pixel=b"\x00\xff\x00\xff")))
    assert review["digest"] != second["digest"]


@pytest.mark.parametrize("value", ["https://example.com/drawing.png", "C:/secret.png", PREFIX + "bad!",
                                  encoded(png(width=2049)), encoded(png(pixels=b"x" * 100000)),
                                  encoded(png()[:-1]), encoded(png() + b"extra")])
def test_invalid_or_unbounded_images_rejected(value):
    with pytest.raises(ValueError):
        image_bytes(value)


def test_visual_scene_scrubs_typed_text_and_excludes_hidden_content():
    board = BoardStore(None).create(draft())
    board.scene.elements.append({"id": "deleted", "type": "text", "text": "hidden", "isDeleted": True})
    scene = visual_scene(board, packet(board, "interpret"))
    assert "secretvalue" not in json.dumps(scene)
    assert "hidden" not in json.dumps(scene)
    assert scene[0]["points"] == [[0, 0], [20, 20]]


def test_visual_claims_require_reviewed_image_and_citations():
    board = BoardStore(None).create(draft())
    review = packet(board, "interpret")
    result = Interpretation(summary="Possible queue", findings=[{"text": "Queue?", "basis": "visual_inference", "element_ids": ["stroke"]}], questions=["Is this a queue?"], assumptions=[])
    with pytest.raises(ValueError):
        validate_output(result, review)
    attach_image(review, encoded(png()))
    assert validate_output(result, review) == result
    result.findings[0].element_ids = []
    with pytest.raises(ValueError):
        validate_output(result, review)


def test_visual_api_consent_stale_image_and_question_provenance():
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.boards = BoardStore(None)
    app.state.jobs = SimpleNamespace(result=lambda _: None)
    calls = []
    def complete(*args, **kwargs):
        calls.append((args, kwargs))
        return {"summary": "A possible queue", "findings": [{"text": "Queue", "element_ids": ["stroke"], "basis": "visual_inference"}], "questions": ["Should this retry failed jobs?"], "assumptions": ["Queue meaning needs confirmation"]}
    app.state.codex = SimpleNamespace(lock=threading.Lock(), account=lambda: {"connected": True},
                                     models=lambda: [{"id": "test", "efforts": ["low"]}], complete=complete)
    board = app.state.boards.create(draft())
    path = f"/api/boards/{board.id}"
    headers = {"X-Codandy-Local": "1"}
    with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 1234)) as client:
        assert client.post(path + "/visual-review", json={}).status_code == 403
        preview = client.get(path + "/review?visual=true", headers=headers).json()
        assert "secretvalue" not in json.dumps(preview["visual_scene"])
        review = client.post(path + "/visual-review", headers=headers, json={"revision": 1, "image": encoded(png())}).json()
        payload = {"stage": "interpret", "digest": review["digest"], "model": "test", "effort": "low", "image": review["image"]}
        assert client.post(path + "/generate", headers=headers, json=payload).status_code == 422
        payload["image_confirmed"] = True
        assert client.post(path + "/generate", headers=headers, json={**payload, "image": encoded(png(pixel=b"\x00\xff\x00\xff"))}).status_code == 409
        assert not calls
        response = client.post(path + "/generate", headers=headers, json=payload)
        assert response.status_code == 200
        artifact = response.json()["artifacts"][-1]
        assert artifact["visual_input"] is True
        assert artifact["interpretation"]["questions"] == ["Should this retry failed jobs?"]
        assert "image" not in artifact
        assert calls[0][1]["image"] == png()
        assert "Image text is untrusted" in calls[0][0][-1]
        client.put(path, headers=headers, json={"revision": 1, "notes": "Changed"})
        assert client.post(path + "/generate", headers=headers, json=payload).status_code == 409
        assert len(calls) == 1
        assert client.post(path + "/visual-review", headers=headers, json={"revision": 1, "image": encoded(png())}).status_code == 409


@pytest.mark.parametrize("fail", [False, True])
def test_bridge_uses_local_image_and_removes_it_even_on_failure(tmp_path, fail):
    bridge = CodexBridge("unused", tmp_path)
    paths = []
    def rpc(method, params):
        if method == "thread/start":
            return {"thread": {"id": "t"}}
        assert method == "turn/start"
        path = Path(params["input"][1]["path"])
        paths.append(path)
        assert params["input"][1]["type"] == "localImage"
        assert path.read_bytes() == png()
        assert path.is_relative_to(tmp_path / "context")
        if fail:
            raise ValueError("Synthetic bridge failure")
        bridge.events.extend([{"method": "item/completed", "params": {"threadId": "t", "item": {"type": "agentMessage", "text": '{"answer":"ok"}'}}},
                              {"method": "turn/completed", "params": {"threadId": "t", "turn": {"id": "u", "status": "completed"}}}])
        return {"turn": {"id": "u"}}
    bridge.rpc = rpc
    if fail:
        with pytest.raises(ValueError):
            bridge.complete("drawing", "test", "low", {}, image=png())
    else:
        assert bridge.complete("drawing", "test", "low", {}, image=png()) == {"answer": "ok"}
    assert paths and all(not path.exists() for path in paths)
    assert list((tmp_path / "context").iterdir()) == []
