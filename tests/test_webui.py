import pytest
from fastapi.testclient import TestClient
from webui.app import create_app


def test_create_session():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    assert data["status"] == "running"


def test_get_session_status():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    sid = resp.json()["session_id"]
    resp2 = client.get(f"/sessions/{sid}")
    assert resp2.status_code == 200
    assert resp2.json()["status"] in ("running", "done", "aborted")


def test_abort_session():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    sid = resp.json()["session_id"]
    resp2 = client.post(f"/sessions/{sid}/abort")
    assert resp2.status_code == 200


def test_max_concurrent_sessions():
    app = create_app(config_path=None, max_concurrent=1)
    client = TestClient(app)
    client.post("/sessions", json={"task": "task1"})
    resp = client.post("/sessions", json={"task": "task2"})
    assert resp.status_code == 429


def test_approve_session():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    sid = resp.json()["session_id"]
    resp2 = client.post(f"/sessions/{sid}/approve", json={"decision": "approve"})
    assert resp2.status_code == 200
    assert resp2.json()["approved"] is True


def test_get_unknown_session_404():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.get("/sessions/does-not-exist")
    assert resp.status_code == 404


def test_websocket_stream():
    app = create_app(config_path=None)
    client = TestClient(app)
    resp = client.post("/sessions", json={"task": "fix test"})
    sid = resp.json()["session_id"]
    with client.websocket_connect(f"/sessions/{sid}/stream") as ws:
        data = ws.receive_json()
        assert data["session_id"] == sid
        assert data["status"] in ("running", "done", "aborted")


def test_websocket_stream_unknown_session():
    app = create_app(config_path=None)
    client = TestClient(app)
    with pytest.raises(Exception):
        with client.websocket_connect("/sessions/unknown/stream") as ws:
            ws.receive_json()
