from __future__ import annotations
import os
import tempfile
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from webui.session_registry import SessionRegistry
from webui.routes import register_stream_route
from harness.config import load_config


class CreateSessionRequest(BaseModel):
    task: str
    seed: str | None = None


class ApproveRequest(BaseModel):
    decision: str  # "approve" | "deny"


def create_app(config_path: str | None = None, max_concurrent: int | None = None):
    cfg = load_config(config_path)
    if max_concurrent is None:
        max_concurrent = cfg.max_concurrent_sessions
    app = FastAPI()
    registry = SessionRegistry(max_concurrent=max_concurrent)

    @app.post("/sessions")
    async def create_session(req: CreateSessionRequest):
        tmpdir = tempfile.mkdtemp()
        sid = registry.create(req.task, tmpdir)
        if sid is None:
            raise HTTPException(status_code=429, detail="Too many concurrent sessions")
        # In real implementation, would start AgentRunner here
        # For now, mark as done immediately for testing
        registry.finish(sid)
        return {"session_id": sid, "status": "running"}

    @app.get("/sessions/{sid}")
    async def get_session(sid: str):
        s = registry.get(sid)
        if s is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"session_id": sid, "status": s["state"], "task": s["task"]}

    @app.post("/sessions/{sid}/approve")
    async def approve(sid: str, req: ApproveRequest):
        s = registry.get(sid)
        if s is None:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"session_id": sid, "approved": req.decision == "approve"}

    @app.post("/sessions/{sid}/abort")
    async def abort(sid: str):
        if not registry.abort(sid):
            raise HTTPException(status_code=404, detail="Session not found")
        return {"session_id": sid, "status": "aborted"}

    # WebSocket streaming endpoint: GET /sessions/{sid}/stream
    register_stream_route(app, registry)

    # Serve static files if directory exists
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    return app
