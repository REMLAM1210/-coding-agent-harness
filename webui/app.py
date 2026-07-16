from __future__ import annotations
import asyncio
import concurrent.futures
import dataclasses
import os
import tempfile
from enum import Enum
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from webui.session_registry import SessionRegistry
from webui.routes import register_stream_route
from harness.config import load_config
from harness.models import (
    Workspace, Action, Decision, DecisionType, LoopFinished,
)
from harness.agent_runner import AgentRunner
from harness.tools.base import ToolDispatcher
from harness.tools.file_tools import ReadFileTool, WriteFileTool, ListFilesTool
from harness.tools.shell_tool import RunShellTool
from harness.tools.feedback_tools import RunTestsTool, RunLintTool, RunTypeCheckTool
from harness.governance.guardrail import Guardrail
from harness.governance.sandbox import Sandbox
from harness.governance.hitl import ApprovalResolver
from harness.feedback.validators import PytestValidator, RuffValidator, MypyValidator
from harness.feedback.classifier import Classifier
from harness.feedback.feedback_loop import FeedbackLoop
from harness.memory.store import MemoryStore
from harness.llm.mock_client import MockLLMClient


class CreateSessionRequest(BaseModel):
    task: str
    seed: str | None = None


class ApproveRequest(BaseModel):
    decision: str  # "approve" | "deny"


def _event_to_dict(event) -> dict:
    def _convert(obj):
        if isinstance(obj, Enum):
            return obj.value
        if dataclasses.is_dataclass(obj):
            return {f.name: _convert(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
        if isinstance(obj, list):
            return [_convert(v) for v in obj]
        if isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        return obj
    result = _convert(event)
    if isinstance(result, dict):
        result["type"] = type(event).__name__
    return result


class SessionEventSink:
    def __init__(self, session: dict):
        self._session = session

    def emit(self, event) -> None:
        d = _event_to_dict(event)
        self._session["events"].append(d)
        if isinstance(event, LoopFinished):
            self._session["state"] = "done"


class FutureApprovalResolver(ApprovalResolver):
    def __init__(self, timeout: int = 300):
        self._future: concurrent.futures.Future | None = None
        self._timeout = timeout

    def request_approval(self, action: Action) -> Decision:
        self._future = concurrent.futures.Future()
        return self._future.result(timeout=self._timeout)

    def resolve(self, decision: Decision) -> bool:
        if self._future is not None and not self._future.done():
            self._future.set_result(decision)
            return True
        return False

    @property
    def pending(self) -> bool:
        return self._future is not None and not self._future.done()


def _default_llm_factory():
    try:
        from credman.store import CredentialStore
        store = CredentialStore()
        key = store.get_key()
        if key:
            from harness.llm.real_client import RealLLMClient
            return RealLLMClient(
                api_key=key,
                base_url="https://njusehub.info/v1",
                model="gpt-4o-mini",
            )
    except Exception:
        pass
    return MockLLMClient(actions=[Action(type="Done", args={"summary": "no LLM configured"})])


def create_app(config_path: str | None = None, max_concurrent: int | None = None,
               llm_client_factory=None):
    cfg = load_config(config_path)
    if max_concurrent is None:
        max_concurrent = cfg.max_concurrent_sessions
    app = FastAPI()
    registry = SessionRegistry(max_concurrent=max_concurrent)

    if llm_client_factory is None:
        llm_client_factory = _default_llm_factory

    @app.post("/sessions")
    async def create_session(req: CreateSessionRequest):
        tmpdir = tempfile.mkdtemp()
        sid = registry.create(req.task, tmpdir)
        if sid is None:
            raise HTTPException(status_code=429, detail="Too many concurrent sessions")

        session = registry.get(sid)

        approval_resolver = FutureApprovalResolver(timeout=cfg.hitl_timeout)
        session["approval_resolver"] = approval_resolver

        sink = SessionEventSink(session)

        tools = [
            ReadFileTool(), WriteFileTool(), ListFilesTool(),
            RunShellTool(timeout=cfg.sandbox_timeout),
            RunTestsTool(timeout=cfg.sandbox_timeout),
            RunLintTool(timeout=cfg.sandbox_timeout),
            RunTypeCheckTool(timeout=cfg.sandbox_timeout),
        ]
        guardrail = Guardrail(rules=cfg.guardrail_rules)
        sandbox = Sandbox(tools=tools, timeout=cfg.sandbox_timeout, env_whitelist=cfg.sandbox_env_whitelist)
        td = ToolDispatcher(
            guardrail=guardrail, sandbox=sandbox,
            approval_resolver=approval_resolver, event_sink=sink,
        )
        llm = llm_client_factory()
        classifier = Classifier(hints=cfg.hints)
        fl = FeedbackLoop(
            max_iterations=cfg.max_iterations,
            escalation_threshold=cfg.feedback_thresholds["escalation_threshold"],
        )
        memory = MemoryStore(workspace_dir=tmpdir)

        runner = AgentRunner(
            llm_client=llm, dispatcher=td,
            validators={
                "RunTests": PytestValidator(),
                "RunLint": RuffValidator(),
                "RunTypeCheck": MypyValidator(),
            },
            classifier=classifier, feedback_loop=fl,
            config=cfg, event_sink=sink, memory_store=memory,
        )

        async def _run_agent():
            try:
                await asyncio.to_thread(runner.run, req.task, Workspace(cwd=tmpdir))
            except Exception:
                session["state"] = "done"

        asyncio.create_task(_run_agent())

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
        resolver = s.get("approval_resolver")
        verdict = DecisionType.ALLOW if req.decision == "approve" else DecisionType.DENY
        decision = Decision(verdict=verdict, reason="" if req.decision == "approve" else "approval_denied")
        if resolver is not None:
            resolver.resolve(decision)
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

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/")
    async def root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/index.html")

    return app
