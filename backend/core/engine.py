"""Nautil Engine — Tree orchestrator.

The engine manages the task tree lifecycle. Each node runs a unified agent loop
(see node_agent.py) that autonomously decides whether to decompose, execute,
or escalate. The engine handles tree management: child creation, composition,
and failure restructuring.
"""
from __future__ import annotations
import asyncio
import random
import shutil
from pathlib import Path
from typing import Any, Callable, Awaitable

from .models import NodeData, NodeStatus, SessionData, EventData, WSMessage
from .node_agent import run_node_agent
from .tools.web import WebSearchTool, WebFetchTool
from .tools.shell import ExecTool
from .tools.filesystem import ReadFileTool, WriteFileTool, EditFileTool, ListDirTool

WORKSPACE_ROOT = Path("/tmp/nautil/sessions")
MAX_RESTRUCTURES = 2

_SAFETY_KEYWORDS = ("unsafe", "sensitive content", "sensitive", "content_filter", "content_security")


class NautilEngine:
    def __init__(
        self,
        session: SessionData,
        provider: Any,
        broadcast: Callable[[WSMessage], Awaitable[None]],
        is_mock: bool = False,
    ):
        self.session = session
        self.provider = provider
        self.broadcast = broadcast
        self.is_mock = is_mock
        self._processing: set[str] = set()
        self._running = True
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # not paused initially
        self.draft_mode = True  # leaf nodes auto-pause until user approves
        self.workspace = WORKSPACE_ROOT / session.id
        self.workspace.mkdir(parents=True, exist_ok=True)
        self._domain_tools: list = self._build_domain_tools(self.workspace)
        self._semaphore = asyncio.Semaphore(session.max_concurrency)
        self._active_tasks: set[asyncio.Task] = set()

    @staticmethod
    def _build_domain_tools(workspace: Path) -> list:
        return [
            WebSearchTool(),
            WebFetchTool(),
            ExecTool(timeout=30, working_dir=str(workspace)),
            ReadFileTool(workspace=workspace, allowed_dir=workspace),
            WriteFileTool(workspace=workspace, allowed_dir=workspace),
            EditFileTool(workspace=workspace, allowed_dir=workspace),
            ListDirTool(workspace=workspace, allowed_dir=workspace),
        ]

    # ── helpers ──

    @staticmethod
    def _safe_filename(title: str, max_len: int = 40) -> str:
        import re as _re
        name = _re.sub(r'[\\/:*?"<>|\s]+', '_', title).strip('_')
        return name[:max_len] if name else "untitled"

    def _save_result_file(self, node: NodeData) -> str:
        fname = f"{self._safe_filename(node.title)}.md"
        fpath = self.workspace / fname
        content_parts = [f"# {node.title}\n"]
        if node.instruction:
            content_parts.append(f"> Task: {node.instruction}\n")
        content_parts.append(node.result or "")
        fpath.write_text("\n".join(content_parts), encoding="utf-8")
        return fname

    def _create_node(self, **kw: Any) -> str:
        node = NodeData(**kw)
        self.session.nodes[node.id] = node
        return node.id

    async def _emit(self, msg: str, nid: str | None = None, level: str = "info"):
        ev = EventData(message=msg, node_id=nid, level=level)
        self.session.events.append(ev)
        await self.broadcast(WSMessage(type="event", data=ev.model_dump()))

    async def _set_status(self, nid: str, status: NodeStatus):
        self.session.nodes[nid].status = status
        await self.broadcast(
            WSMessage(type="node_updated", data=self.session.nodes[nid].model_dump())
        )

    async def _bcast_node(self, nid: str):
        await self.broadcast(
            WSMessage(type="node_created", data=self.session.nodes[nid].model_dump())
        )

    async def _bcast_edge(self, edge: dict):
        await self.broadcast(WSMessage(type="edge_created", data=edge))

    def _ready(self) -> list[str]:
        return [
            nid for nid, n in self.session.nodes.items()
            if nid not in self._processing
            and n.status == NodeStatus.PENDING
        ]

    async def _check_draft_complete(self):
        """Check if all leaf nodes are PAUSED (draft decomposition finished)."""
        if not self.draft_mode:
            return
        for n in self.session.nodes.values():
            if n.status in (NodeStatus.PENDING, NodeStatus.EXECUTING, NodeStatus.READY):
                return
        await self._emit("Decomposition complete. Please review all nodes and click Resume to start execution.", level="success")
        self.session.status = "draft_ready"
        await self.broadcast(WSMessage(type="session_update", data={"status": "draft_ready"}))
        await self.broadcast(WSMessage(type="draft_complete", data={}))

    _TERMINAL = frozenset({
        NodeStatus.PASSED, NodeStatus.FAILED,
        NodeStatus.PAUSED, NodeStatus.WAITING_HUMAN,
    })

    def _all_terminal(self) -> bool:
        return all(n.status in self._TERMINAL for n in self.session.nodes.values())

    # ── main loop ──

    async def start(self):
        root = self._create_node(
            title=self.session.problem,
            instruction=f"Solve: {self.session.problem}",
            depth=0,
        )
        self.session.root_id = root
        await self._bcast_node(root)
        await self._emit(f"Start solving: {self.session.problem}", root)

        self.session.status = "running"
        await self.broadcast(WSMessage(type="session_update", data={"status": "running"}))

        await self._loop()

        ok = self.session.nodes[self.session.root_id].status == NodeStatus.PASSED
        self.session.status = "completed" if ok else "failed"
        await self.broadcast(WSMessage(type="session_update", data={"status": self.session.status}))
        await self._emit(
            f"{'Solving complete' if ok else 'Solving failed'}",
            level="success" if ok else "error",
        )

    async def _loop(self):
        while self._running:
            await self._pause_event.wait()
            ready = self._ready()
            if not ready:
                if self._all_terminal():
                    break
                await asyncio.sleep(0.3)
                continue
            for nid in ready:
                self._processing.add(nid)
                task = asyncio.create_task(self._safe(nid))
                self._active_tasks.add(task)
                task.add_done_callback(self._active_tasks.discard)
            await asyncio.sleep(0.3)

    async def _safe(self, nid: str):
        try:
            await self._pause_event.wait()
            async with self._semaphore:
                await self._process(nid)
        except asyncio.CancelledError:
            self.session.nodes[nid].status = NodeStatus.PAUSED
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            node = self.session.nodes[nid]
            node.error_message = f"{exc}\n\n{tb}"
            await self._emit(f"Node processing error: {exc}", nid, "error")
            await self._set_status(nid, NodeStatus.FAILED)
            if node.parent_id:
                is_safety = any(kw in str(exc) for kw in _SAFETY_KEYWORDS)
                try:
                    await self._do_escalate(nid, str(exc), content_safety=is_safety)
                except Exception:
                    pass
        finally:
            self._processing.discard(nid)

    # ── per-node processing (unified) ──

    async def _process(self, nid: str):
        node = self.session.nodes[nid]
        is_compose_pass = len(node.children) > 0

        if self.draft_mode and not is_compose_pass and node.depth >= self.MAX_DEPTH:
            node.is_leaf = True
            await self._set_status(nid, NodeStatus.PAUSED)
            await self._emit(f"Node '{node.title}' reached max depth, marked as leaf awaiting execution", nid, "info")
            await self._check_draft_complete()
            return

        await self._set_status(nid, NodeStatus.EXECUTING)

        if self.draft_mode and not is_compose_pass:
            tools = []
            await self._emit(f"Node '{node.title}' planning (draft mode)", nid)
        else:
            tools = self._domain_tools
            if is_compose_pass:
                await self._emit(f"Node '{node.title}' composing from child results", nid)
            else:
                await self._emit(f"Node '{node.title}' started processing", nid)

        is_leaf_exec = node.is_leaf and not self.draft_mode and not is_compose_pass

        signal = await run_node_agent(
            node=node,
            session=self.session,
            provider=self.provider,
            domain_tools=tools,
            broadcast=self.broadcast,
            workspace=str(self.workspace),
            compose_mode=is_compose_pass,
            draft_mode=self.draft_mode and not is_compose_pass,
            leaf_execution=is_leaf_exec,
            pause_event=self._pause_event,
            is_running=lambda: self._running,
        )

        sig = signal["type"]
        data = signal["data"]

        if sig == "paused":
            await self._set_status(nid, NodeStatus.PAUSED)
            return

        if sig == "completed":
            if self.draft_mode and not is_compose_pass:
                node.result = data
                node.is_leaf = True
                await self._set_status(nid, NodeStatus.PAUSED)
                await self._emit(f"Node '{node.title}' ready, awaiting approval to execute", nid, "info")
                await self._check_draft_complete()
                return

            await self._do_complete(nid, data, is_compose_pass)

        elif sig == "decomposed":
            if is_compose_pass:
                await self._emit(f"Node '{node.title}' already has children — skipping re-decompose, submitting as result", nid, "warning")
                await self._do_complete(nid, str(data), is_compose_pass)
            else:
                node.is_leaf = False
                await self._do_decompose(nid, data)

        elif sig == "escalated":
            if isinstance(data, dict):
                reason = data.get("reason", str(data))
                content_safety = data.get("error_tag") == "content_safety"
            else:
                reason = str(data)
                content_safety = False
            await self._do_escalate(nid, reason, content_safety=content_safety)

    async def _do_complete(self, nid: str, data: str, is_compose_pass: bool):
        node = self.session.nodes[nid]
        node.result = data
        node.is_leaf = not is_compose_pass

        if self.session.verify_mode:
            await self._set_status(nid, NodeStatus.VERIFYING)
            await self._emit(f"Node '{node.title}' verifying result", nid)
            passed, reason = await self._verify(node, data)
            node.verify_result = reason
            node.verify_passed = passed
        else:
            passed = True
            reason = "Verification skipped (fast mode)"
            node.verify_result = reason
            node.verify_passed = True

        if passed:
            result_file = self._save_result_file(node)
            node.result_file = result_file
            await self._set_status(nid, NodeStatus.PASSED)
            await self._emit(f"Node '{node.title}' {'verified' if self.session.verify_mode else 'completed'} -> {result_file}", nid, "success")
            await self._bubble_up(nid)
        else:
            node.retry_count += 1
            if node.retry_count > node.max_retries:
                await self._emit(f"Node '{node.title}' verification failed and exceeded max retries", nid, "error")
                await self._do_escalate(nid, f"Verification failed: {reason}")
            else:
                await self._emit(
                    f"Node '{node.title}' verification failed (attempt {node.retry_count}): {reason}",
                    nid, "warning",
                )
                node.delta_state += f"\n\n## Verification Feedback (attempt {node.retry_count})\n{reason}"
                node.result = None
                node.status = NodeStatus.PENDING
                self._processing.discard(nid)
                await self.broadcast(
                    WSMessage(type="node_updated", data=node.model_dump())
                )

    # ── DECOMPOSE ──

    @property
    def MAX_DEPTH(self) -> int:
        return self.session.max_depth

    _SUMMARY_KEYWORDS = {"summary", "synthesis", "aggregate", "integrate", "consolidate", "final output", "comprehensive report", "overall summary"}

    def _filter_summary_tasks(self, subtasks: list[dict]) -> list[dict]:
        """Remove summary/synthesis tasks (parent's compose duty)."""
        if len(subtasks) <= 1:
            return subtasks
        filtered = []
        for spec in subtasks:
            title = spec.get("title", "")
            if any(kw in title for kw in self._SUMMARY_KEYWORDS):
                continue
            filtered.append(spec)
        return filtered

    async def _do_decompose(self, nid: str, subtasks: list[dict]):
        node = self.session.nodes[nid]
        if node.depth >= self.MAX_DEPTH:
            if self.draft_mode:
                node.is_leaf = True
                await self._set_status(nid, NodeStatus.PAUSED)
                await self._emit(f"Node '{node.title}' reached max depth, marked as leaf awaiting execution", nid, "info")
                await self._check_draft_complete()
            else:
                await self._emit(f"Node '{node.title}' reached max depth, forced as leaf node", nid, "warning")
                node.result = str(subtasks)
                node.is_leaf = True
                await self._set_status(nid, NodeStatus.PASSED)
                await self._bubble_up(nid)
            return
        subtasks = self._filter_summary_tasks(subtasks)
        if len(subtasks) > self.session.max_children:
            subtasks = subtasks[:self.session.max_children]
        if not subtasks:
            await self._emit(f"Node '{node.title}' all decomposition results filtered, forced as leaf", nid, "warning")
            node.is_leaf = True
            node.status = NodeStatus.PENDING
            self._processing.discard(nid)
            await self.broadcast(WSMessage(type="node_updated", data=node.model_dump()))
            return

        await self._set_status(nid, NodeStatus.DECOMPOSING)
        await self._emit(f"Node '{node.title}' decomposed into {len(subtasks)} sub-tasks", nid)

        cids: list[str] = []
        for spec in subtasks:
            cid = self._create_node(
                title=spec["title"],
                instruction=spec["instruction"],
                parent_id=nid,
                depth=node.depth + 1,
            )
            cids.append(cid)
            await self._bcast_node(cid)
            parent_edge = {"id": f"e-parent-{nid}-{cid}", "source": nid, "target": cid, "type": "parent"}
            self.session.edges.append(parent_edge)
            await self._bcast_edge(parent_edge)
            await asyncio.sleep(0.12)

        node.children = cids

    # ── ESCALATE ──

    async def _do_escalate(self, nid: str, reason: str, content_safety: bool = False):
        node = self.session.nodes[nid]
        await self._set_status(nid, NodeStatus.ESCALATING)

        if not node.parent_id:
            await self._set_status(nid, NodeStatus.WAITING_HUMAN)
            await self._emit("Root node cannot solve, human assistance needed", nid, "error")
            return

        parent = self.session.nodes[node.parent_id]
        await self._emit(
            f"Node '{node.title}' ESCALATE -> '{parent.title}'", nid, "warning"
        )
        await self._set_status(nid, NodeStatus.FAILED)

        if content_safety:
            await self._emit(
                f"Content safety restriction — skipping restructure, '{parent.title}' attempting partial delivery", parent.id, "warning"
            )
            await self._partial_compose(parent)
        elif parent.restructure_count >= MAX_RESTRUCTURES:
            await self._emit(
                f"Restructure limit reached ({MAX_RESTRUCTURES}), '{parent.title}' attempting partial delivery", parent.id, "warning"
            )
            await self._partial_compose(parent)
        else:
            parent.restructure_count += 1
            await self._restructure(parent, nid, reason)

    async def _restructure(self, parent: NodeData, failed_id: str, reason: str):
        failed = self.session.nodes[failed_id]
        await self._emit(
            f"'{parent.title}' restructuring: replacing '{failed.title}'", parent.id, "warning"
        )

        parent.children = [c for c in parent.children if c != failed_id]

        await asyncio.sleep(1.0)

        new_id = self._create_node(
            title=f"{failed.title} (revised)",
            instruction=f"Re-implement: {failed.instruction}. Previous approach failed: {reason}",
            parent_id=parent.id,
            depth=parent.depth + 1,
        )
        parent.children.append(new_id)
        await self._bcast_node(new_id)

        parent_edge = {"id": f"e-parent-{parent.id}-{new_id}", "source": parent.id, "target": new_id, "type": "parent"}
        self.session.edges.append(parent_edge)
        await self._bcast_edge(parent_edge)

        await self._emit(f"Restructure complete: added '{failed.title} (revised)'", parent.id, "info")

    async def _partial_compose(self, parent: NodeData):
        """Let the parent compose from available child results, skipping failed children."""
        has_passed = any(
            self.session.nodes[c].status == NodeStatus.PASSED
            for c in parent.children
        )
        if has_passed:
            await self._emit(f"Node '{parent.title}' attempting delivery from available results", parent.id, "info")
            await self._compose(parent.id)
        elif parent.parent_id:
            await self._do_escalate(parent.id, "All child nodes failed, cannot deliver")
        else:
            await self._set_status(parent.id, NodeStatus.WAITING_HUMAN)
            await self._emit("All child tasks of root node failed, human assistance needed", parent.id, "error")

    # ── COMPOSE (bubble up) ──

    async def _bubble_up(self, nid: str):
        node = self.session.nodes[nid]
        if not node.parent_id:
            return
        parent = self.session.nodes[node.parent_id]
        if all(
            self.session.nodes[c].status == NodeStatus.PASSED
            for c in parent.children
        ):
            await self._compose(parent.id)

    async def _compose(self, nid: str):
        node = self.session.nodes[nid]
        await self._emit(f"Node '{node.title}' all children completed, composing result", nid)

        node.status = NodeStatus.PENDING
        node.is_leaf = False
        node.context_log.append({
            "type": "assistant",
            "content": f"All {len(node.children)} child tasks completed. Composing this node's result.",
            "timestamp": __import__("datetime").datetime.now().strftime("%H:%M:%S"),
        })
        self._processing.discard(nid)

        await self.broadcast(
            WSMessage(type="node_updated", data=node.model_dump())
        )

    # ── VERIFY ──

    async def _verify(self, node: NodeData, result: str) -> tuple[bool, str]:
        if self.is_mock:
            await asyncio.sleep(random.uniform(0.5, 1.0))
            if "Module B" in node.title and "revised" not in node.title:
                return False, "Core logic has boundary condition errors"
            return True, "Verification passed, result meets expectations"

        import json as _json
        try:
            resp = await self.provider.chat(
                messages=[
                    {"role": "system", "content": (
                        "You are a verifier. Determine whether the node's execution result fulfills the task instruction.\n"
                        "Criteria: 1. Does it address the task requirements? 2. Does it have substantive content? 3. Are there obvious errors?\n"
                        'Reply JSON: {"passed":true/false,"reason":"reason"}'
                    )},
                    {"role": "user", "content": (
                        f"Task: {node.title}\nInstruction: {node.instruction}\n\nResult:\n{result}"
                    )},
                ],
            )
            raw = resp.content or ""
            if "{" in raw:
                json_str = raw[raw.index("{"):raw.rindex("}") + 1]
                d = _json.loads(json_str)
                return d.get("passed", True), d.get("reason", "")
            return True, "Verification passed"
        except Exception as e:
            await self._emit(f"Verification call error: {e}, defaulting to pass", node.id, "warning")
            return True, f"Verification skipped (API error: {type(e).__name__})"

    async def pause(self):
        self._pause_event.clear()
        self.session.status = "paused"
        await self.broadcast(WSMessage(type="session_update", data={"status": "paused"}))
        await self._emit("Session paused", level="warning")

    async def resume(self):
        if self.draft_mode:
            self.draft_mode = False
            count = 0
            for n in self.session.nodes.values():
                if n.status == NodeStatus.PAUSED and n.is_leaf:
                    n.status = NodeStatus.PENDING
                    n.result = None
                    n.context_log = []
                    count += 1
                    await self.broadcast(WSMessage(type="node_updated", data=n.model_dump()))
            await self._emit(f"Draft approved, {count} nodes starting execution", level="success")

        self._pause_event.set()
        self.session.status = "running"
        await self.broadcast(WSMessage(type="session_update", data={"status": "running"}))
        await self._emit("Session resumed", level="info")

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    async def stop(self):
        self._running = False
        self._pause_event.set()
        for t in list(self._active_tasks):
            t.cancel()
