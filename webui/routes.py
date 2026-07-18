from __future__ import annotations
from fastapi import WebSocket, WebSocketDisconnect


def register_stream_route(app, registry) -> None:
    """Register the WebSocket streaming endpoint for a session.

    GET /sessions/{sid}/stream (WebSocket): streams agent events for the session.
    Sends the current session state immediately, replays any buffered events,
    then closes if the session is terminal (done/aborted). For running sessions
    the socket stays open until the client disconnects.
    """

    @app.websocket("/sessions/{sid}/stream")
    async def stream(ws: WebSocket, sid: str):
        s = registry.get(sid)
        if s is None:
            await ws.close(code=1008)
            return
        await ws.accept()
        await ws.send_json({"session_id": sid, "status": s["state"], "task": s["task"]})
        for ev in s.get("events", []):
            await ws.send_json(ev)
        if s["state"] in ("done", "aborted"):
            await ws.close()
            return
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            return
