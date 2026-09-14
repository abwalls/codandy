"""Opt-in live GitHub smoke check. Run from backend: python smoke.py."""

import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models import AtlasDocument
from app.settings import settings


def main():
    with tempfile.TemporaryDirectory(prefix="atlas-smoke-") as workspace:
        settings.workspace_root = workspace
        # The API only answers to local host names (DNS-rebinding protection).
        with TestClient(app, base_url="http://localhost") as client:
            response = client.post("/api/analyses", json={"source": {
                "url": "https://github.com/microsoft/TypeScript-React-Starter"}})
            response.raise_for_status()
            job_id = response.json()["id"]
            deadline = time.monotonic() + 260
            while time.monotonic() < deadline:
                job = client.get(f"/api/analyses/{job_id}").json()
                if job["status"] in {"complete", "failed"}:
                    break
                time.sleep(0.25)
            if job["status"] != "complete":
                raise RuntimeError(job.get("error") or "Smoke test deadline exceeded")
            response = client.get(f"/api/analyses/{job_id}/atlas")
            response.raise_for_status()
            atlas = AtlasDocument.model_validate(response.json())
            assert atlas.repository.get("commit")
            assert atlas.counts["symbols"] > 0
            assert "React" in atlas.technologies
            assert not list(Path(workspace).iterdir()), "Clone workspace was not cleaned up"
            events = client.get(f"/api/analyses/{job_id}/events")
            assert '"status":"complete"' in events.text
            # The viewer must still serve source after the workspace is destroyed.
            symbol = next(node for node in atlas.nodes
                          if node.kind in {"function", "class", "method"} and node.evidence[0].lines)
            source = client.get(f"/api/analyses/{job_id}/source",
                                params={"path": symbol.evidence[0].path})
            source.raise_for_status()
            captured = source.json()
            assert captured["lines"] > 0 and captured["text"]
            denied = client.get(f"/api/analyses/{job_id}/source",
                                params={"path": "../../../etc/passwd"})
            assert denied.status_code == 404
            print({"status": "complete", "commit": atlas.repository["commit"],
                   "counts": atlas.counts, "technologies": atlas.technologies,
                   "workspace_cleaned": True,
                   "source": {"path": captured["path"], "lines": captured["lines"],
                              "evidence": symbol.evidence[0].lines,
                              "truncated": captured["truncated"]}})


if __name__ == "__main__":
    main()
