from __future__ import annotations
import asyncio
import tarfile
import io
from contextlib import asynccontextmanager

from urllib.parse import quote

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .core.models import SessionData, NodeStatus, WSMessage
from .core.engine import NautilEngine, WORKSPACE_ROOT
from .llm.provider import create_provider


# ── state ──

sessions: dict[str, SessionData] = {}
engines: dict[str, NautilEngine] = {}


class ConnMgr:
    def __init__(self):
        self.pool: dict[str, list[WebSocket]] = {}

    async def connect(self, sid: str, ws: WebSocket):
        await ws.accept()
        self.pool.setdefault(sid, []).append(ws)

    def disconnect(self, sid: str, ws: WebSocket):
        if sid in self.pool:
            self.pool[sid] = [w for w in self.pool[sid] if w is not ws]

    async def broadcast(self, sid: str, msg: WSMessage):
        for ws in list(self.pool.get(sid, [])):
            try:
                await ws.send_json(msg.model_dump())
            except Exception:
                self.pool[sid] = [w for w in self.pool[sid] if w is not ws]


mgr = ConnMgr()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    for eng in engines.values():
        await eng.stop()


app = FastAPI(title="Nautil", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST ──

class CreateReq(BaseModel):
    problem: str
    verify_mode: bool = False
    max_depth: int = 2
    max_concurrency: int = 2
    max_children: int = 5


class FeedbackReq(BaseModel):
    feedback: str


@app.post("/api/sessions")
async def create_session(req: CreateReq):
    s = SessionData(
        problem=req.problem,
        verify_mode=req.verify_mode,
        max_depth=max(1, min(4, req.max_depth)),
        max_concurrency=max(1, min(10, req.max_concurrency)),
        max_children=max(3, min(10, req.max_children)),
    )
    sessions[s.id] = s
    return {"session_id": s.id}


@app.get("/api/sessions/{sid}")
async def get_session(sid: str):
    s = sessions.get(sid)
    if not s:
        return {"error": "not found"}
    return s.model_dump()


@app.post("/api/sessions/{sid}/start")
async def start_session(sid: str):
    s = sessions.get(sid)
    if not s:
        return {"error": "not found"}

    provider, is_mock = create_provider(problem=s.problem)

    async def bcast(msg: WSMessage):
        await mgr.broadcast(sid, msg)

    eng = NautilEngine(s, provider, bcast, is_mock=is_mock)
    engines[sid] = eng
    asyncio.create_task(eng.start())
    return {"status": "started"}


@app.post("/api/sessions/{sid}/pause")
async def pause_session(sid: str):
    eng = engines.get(sid)
    if not eng:
        return {"error": "not found"}
    await eng.pause()
    return {"status": "paused"}


@app.post("/api/sessions/{sid}/resume")
async def resume_session(sid: str):
    eng = engines.get(sid)
    if not eng:
        return {"error": "not found"}
    await eng.resume()
    return {"status": "running"}


@app.post("/api/sessions/{sid}/nodes/{nid}/pause")
async def pause_node(sid: str, nid: str):
    s = sessions.get(sid)
    if not s or nid not in s.nodes:
        return {"error": "not found"}
    s.nodes[nid].status = NodeStatus.PAUSED
    await mgr.broadcast(sid, WSMessage(type="node_updated", data=s.nodes[nid].model_dump()))
    return {"status": "paused"}


@app.post("/api/sessions/{sid}/nodes/{nid}/resume")
async def resume_node(sid: str, nid: str):
    s = sessions.get(sid)
    if not s or nid not in s.nodes:
        return {"error": "not found"}
    s.nodes[nid].status = NodeStatus.PENDING
    await mgr.broadcast(sid, WSMessage(type="node_updated", data=s.nodes[nid].model_dump()))
    return {"status": "resumed"}


@app.post("/api/sessions/{sid}/nodes/{nid}/retry")
async def retry_node(sid: str, nid: str):
    s = sessions.get(sid)
    if not s or nid not in s.nodes:
        return {"error": "not found"}
    node = s.nodes[nid]
    node.retry_count = 0
    node.status = NodeStatus.PENDING
    await mgr.broadcast(sid, WSMessage(type="node_updated", data=node.model_dump()))
    return {"status": "retrying"}


@app.post("/api/sessions/{sid}/nodes/{nid}/feedback")
async def node_feedback(sid: str, nid: str, req: FeedbackReq):
    s = sessions.get(sid)
    if not s or nid not in s.nodes:
        return {"error": "not found"}
    node = s.nodes[nid]
    node.instruction += f"\n\n## Human Feedback\n{req.feedback}"
    node.retry_count = 0
    node.status = NodeStatus.PENDING
    await mgr.broadcast(sid, WSMessage(type="node_updated", data=node.model_dump()))
    return {"status": "feedback applied"}


@app.get("/api/sessions/{sid}/download")
async def download_workspace(sid: str):
    workspace = WORKSPACE_ROOT / sid
    if not workspace.exists():
        return {"error": "workspace not found"}

    try:
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for fpath in sorted(workspace.rglob("*")):
                if fpath.is_file():
                    arcname = str(fpath.relative_to(workspace))
                    tar.add(str(fpath), arcname=arcname)
        buf.seek(0)

        s = sessions.get(sid)
        name = f"nautil-{sid}"
        if s:
            safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in s.problem[:30])
            name = f"nautil-{safe}"

        encoded_name = quote(f"{name}.tar.gz")
        return StreamingResponse(
            buf,
            media_type="application/gzip",
            headers={
                "Content-Disposition": f"attachment; filename=\"{sid}.tar.gz\"; filename*=UTF-8''{encoded_name}",
            },
        )
    except Exception as e:
        return {"error": str(e)}


# ── WebSocket ──

@app.websocket("/ws/{sid}")
async def ws_endpoint(ws: WebSocket, sid: str):
    await mgr.connect(sid, ws)
    try:
        s = sessions.get(sid)
        if s:
            await ws.send_json(
                WSMessage(type="session_state", data=s.model_dump()).model_dump()
            )
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        mgr.disconnect(sid, ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
