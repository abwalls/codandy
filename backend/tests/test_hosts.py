import pytest
from fastapi.testclient import TestClient

from app.hosts import host_name
from app.main import app


@pytest.mark.parametrize(("header", "expected"), [
    ("localhost", "localhost"), ("LOCALHOST:5173", "localhost"), ("127.0.0.1:8000", "127.0.0.1"),
    ("[::1]:8000", "::1"), ("", None), ("evil.test@127.0.0.1", None), ("127.0.0.1/path", None),
    ("[::1", None), ("localhost:99999999", None),
])
def test_host_header_parsing(header, expected):
    assert host_name(header) == expected


def test_rebound_host_names_are_rejected_before_any_route():
    with TestClient(app, base_url="http://localhost") as client:
        assert client.get("/api/analyses").status_code == 200
        for host in ["127.0.0.1:8000", "[::1]:8000"]:
            assert client.get("/api/analyses", headers={"Host": host}).status_code == 200
        # A DNS-rebinding page keeps its own name in Host even after resolving to 127.0.0.1.
        for host in ["rebind.attacker.test", "rebind.attacker.test:8000", "localhost.attacker.test"]:
            rejected = client.get("/api/analyses", headers={"Host": host})
            assert rejected.status_code == 403, host
            assert "approved host name" in rejected.json()["detail"]
        foreign = {"Host": "rebind.attacker.test"}
        assert client.post("/api/analyses/archive", params={"filename": "project.zip"}, content=b"PK",
                           headers={**foreign, "Content-Type": "application/zip"}).status_code == 403
        assert client.get("/api/analyses/00000000-0000-4000-8000-000000000000/source",
                          params={"path": "app.py"}, headers=foreign).status_code == 403
        assert client.delete("/api/analyses/00000000-0000-4000-8000-000000000000",
                             headers=foreign).status_code == 403
