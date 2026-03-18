"""Per-node agent loop: the unified execution model.

Every node — regardless of complexity — runs the same agent loop.
The LLM sees all available tools (structural + domain) and autonomously
decides whether to decompose, execute directly, or escalate.
"""
from __future__ import annotations
import asyncio
import json
from datetime import datetime
from typing import Any, Callable, Awaitable

from .models import NodeData, SessionData, WSMessage
from .tools.registry import ToolRegistry
from .tools.structural import DecomposeTool, SubmitResultTool, EscalateTool

MAX_ITERATIONS = 25

_SAFETY_KEYWORDS = ("unsafe", "sensitive content", "sensitive", "content_filter", "content_security")


async def run_node_agent(
    node: NodeData,
    session: SessionData,
    provider: Any,
    domain_tools: list,
    broadcast: Callable[[WSMessage], Awaitable[None]],
    workspace: str = "",
    compose_mode: bool = False,
    draft_mode: bool = False,
    leaf_execution: bool = False,
    pause_event: asyncio.Event | None = None,
    is_running: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Run an agent loop for a single node.

    Returns ``{"type": "completed"|"decomposed"|"escalated"|"paused", "data": ...}``.
    """
    signal: dict[str, Any] = {"type": None, "data": None}

    registry = ToolRegistry()
    for tool in domain_tools:
        registry.register(tool)
    if not leaf_execution:
        registry.register(DecomposeTool(signal))
    registry.register(SubmitResultTool(signal))
    registry.register(EscalateTool(signal))

    messages = _build_messages(node, session, workspace, compose_mode, draft_mode, leaf_execution)

    def _ts() -> str:
        return datetime.now().strftime("%H:%M:%S")

    for _iteration in range(MAX_ITERATIONS):
        if is_running and not is_running():
            return {"type": "paused", "data": "Task terminated"}
        if pause_event:
            await pause_event.wait()

        try:
            response = await provider.chat(
                messages=messages,
                tools=registry.get_definitions(),
            )
        except Exception as e:
            err_msg = str(e)
            is_safety = any(kw in err_msg for kw in _SAFETY_KEYWORDS)
            error_tag = "content_safety" if is_safety else "runtime"
            entry = {"type": "error", "content": err_msg, "timestamp": _ts()}
            node.context_log.append(entry)
            await broadcast(WSMessage(type="node_log", data={"node_id": node.id, "entry": entry}))
            return {"type": "escalated", "data": {"reason": f"LLM call exception: {err_msg}", "error_tag": error_tag}}

        if response.has_tool_calls:
            tc_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                    },
                }
                for tc in response.tool_calls
            ]
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": tc_dicts,
            })

            if response.content:
                entry = {"type": "assistant", "content": response.content, "timestamp": _ts()}
                node.context_log.append(entry)
                await broadcast(WSMessage(type="node_log", data={"node_id": node.id, "entry": entry}))

            for tc in response.tool_calls:
                if is_running and not is_running():
                    return {"type": "paused", "data": "Task terminated"}
                if pause_event:
                    await pause_event.wait()

                entry_call = {
                    "type": "tool_call",
                    "tool": tc.name,
                    "content": _preview(tc.arguments),
                    "timestamp": _ts(),
                }
                node.context_log.append(entry_call)
                await broadcast(WSMessage(type="node_log", data={"node_id": node.id, "entry": entry_call}))

                result = await registry.execute(tc.name, tc.arguments)
                result_preview = result[:500] + "..." if len(result) > 500 else result
                entry_result = {
                    "type": "tool_result",
                    "tool": tc.name,
                    "content": result_preview,
                    "timestamp": _ts(),
                }
                node.context_log.append(entry_result)
                await broadcast(WSMessage(type="node_log", data={"node_id": node.id, "entry": entry_result}))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result,
                })

                if signal["type"]:
                    return signal
        else:
            if response.content:
                entry = {"type": "assistant", "content": response.content, "timestamp": _ts()}
                node.context_log.append(entry)
                await broadcast(WSMessage(type="node_log", data={"node_id": node.id, "entry": entry}))
                signal["type"] = "completed"
                signal["data"] = response.content
                return signal
            break

    return {"type": "escalated", "data": "Max iterations reached, unable to complete task"}


def _build_messages(node: NodeData, session: SessionData, workspace: str = "", compose_mode: bool = False, draft_mode: bool = False, leaf_execution: bool = False) -> list[dict]:
    ctx_parts: list[str] = []

    chain: list[NodeData] = []
    cur = node
    while cur.parent_id:
        parent = session.nodes.get(cur.parent_id)
        if not parent:
            break
        chain.append(parent)
        cur = parent

    if chain:
        ctx_parts.append("## Parent Task Chain (reference only — focus on current task)")
        ctx_parts.append("Your **primary task** is the Instruction above. The parent/ancestor chain below is for background context only. **Stay focused** on the current node's problem.")
        for a in reversed(chain):
            brief = (a.instruction[:80] + "…") if len(a.instruction or "") > 80 else (a.instruction or "")
            ctx_parts.append(f"- [{a.title}] {brief}")

    if node.delta_state:
        ctx_parts.append("\n## Previous Verification Feedback (refer to on retry)")
        ctx_parts.append(node.delta_state)

    if compose_mode and node.children:
        ctx_parts.append("\n## Child Task Results")
        for cid in node.children:
            child = session.nodes.get(cid)
            if child:
                file_ref = f"(file: {child.result_file})" if child.result_file else ""
                ctx_parts.append(f"### {child.title} {file_ref}\n{child.result or '(no result)'}\n")

    context = "\n".join(ctx_parts) or "(no additional context)"
    is_root = node.parent_id is None

    system = (
        f"You are a worker node in the Nautil problem-solving engine.\n\n"
        f"Current node: {node.title}\n"
        f"Instruction: {node.instruction}\n"
        f"Node depth: {node.depth} (0 = root)\n\n"
        f"Context:\n{context}\n\n"
    )

    if leaf_execution:
        system += (
            f"## Execution Rules (strictly follow)\n\n"
            f"You are a leaf node. The task has been confirmed during planning and is now in the **execution phase**.\n"
            f"**Execute the task directly. Do NOT decompose further.**\n\n"
            f"### How to Execute\n"
            f"- If you already know the answer, output it directly as text\n"
            f"- If external information is needed, use domain tools (web_search/web_fetch/exec, etc.) to gather it, then answer\n"
            f"- You may also call submit_result to explicitly submit your result\n\n"
            f"### When to Escalate\n"
            f"- Required information is missing and cannot be obtained via tools\n"
            f"- Multiple retries have failed\n\n"
        )
    else:
        system += (
            f"## Decision Rules (strictly follow)\n\n"
            f"### Depth Limit\n"
            f"- Max decomposition depth is {session.max_depth}. Current depth = {node.depth}\n"
            f"- **Do NOT call decompose when depth >= {session.max_depth}**\n\n"
            f"### When to Decompose\n"
            f"Call decompose when depth < {session.max_depth} and **any** of the following conditions are met:\n"
            f"- The task involves 2 or more independent sub-domains\n"
            f"- Depth <= 1 and the task description exceeds 20 words\n"
            f"- Keep the number of sub-tasks between 2 and {session.max_children}\n\n"
            f"### Decomposition Rules (critical)\n"
            f"1. **All sub-tasks must be mutually independent and parallelizable**\n"
            f"2. If a sub-task needs further steps internally, let it decompose itself — do not plan dependency chains at the parent level\n"
            f"3. **Do NOT create summary/synthesis/integration sub-tasks** — that is the parent node's own responsibility\n"
            f"4. Each sub-task must carry independent, substantive work\n\n"
            f"### When to Execute Directly as a Leaf Node\n"
            f"When the task is a concrete, directly answerable or actionable item:\n"
            f"- If you already know the answer, output it directly as text (the system will auto-submit it as the result)\n"
            f"- If external information is needed, use domain tools (web_search/web_fetch/exec, etc.) first, then answer\n"
            f"- You may also call submit_result to explicitly submit your result\n\n"
            f"### When to Escalate\n"
            f"- Required information is missing and cannot be obtained via tools\n"
            f"- Multiple retries have failed\n\n"
        )

        if is_root:
            system += (
                f"## Important\n"
                f"You are the **root node**, facing the user's original problem. For any non-trivial problem, you should call decompose to break it into sub-tasks.\n"
                f"Each sub-task should have a clear title and instruction, and be mutually independent and parallelizable.\n\n"
                f"### Decompose Example\n"
                f"User question: \"How to design a high-concurrency flash-sale system?\"\n"
                f"Correct approach -> Call decompose, breaking it into independent parallel sub-tasks:\n"
                f"1. \"Traffic Surge Strategy\" (instruction: research and design rate-limiting, peak-shaving, CDN solutions)\n"
                f"2. \"Inventory Deduction & Consistency\" (instruction: design anti-oversell inventory solutions, including distributed locks, pre-deduction, etc.)\n"
                f"3. \"High-Availability Architecture\" (instruction: design failover, multi-level caching, graceful degradation strategies)\n\n"
            )

    if draft_mode and not compose_mode:
        system += (
            f"## Current Phase: Draft Planning\n"
            f"You are in the draft planning phase. The goal is to **plan the task decomposition structure** without executing any actual work.\n"
            f"Domain tools (web_search, web_fetch, exec, etc.) are only available during execution phase and cannot be called now.\n\n"
            f"### Your Options\n"
            f"- If the task needs further decomposition: call decompose\n"
            f"- If the task is atomic enough to execute directly: reply `ready`\n"
            f"- If the task cannot be completed under current conditions: call escalate\n\n"
        )
    else:
        system += (
            f"## Available Tools\n"
            f"You may use the following tools (full definitions are passed in the tools parameter):\n"
            f"- **Structural tools**: decompose (break into sub-tasks), submit_result (submit result), escalate (propagate failure)\n"
            f"- **Domain tools**: web_search (search), web_fetch (fetch webpage), exec (execute command), "
            f"read_file (read file), write_file (write file), edit_file (edit file), list_dir (list directory)\n\n"
        )

    system += (
        f"## Workspace\n"
        f"Your isolated workspace path: {workspace}\n"
        f"All file operations (read/write/edit/list) are restricted to this directory. exec commands run here by default.\n"
        f"You may create files in the workspace to save intermediate results, code, notes, etc.\n\n"
        f"Begin working now."
    )

    if compose_mode:
        file_list = []
        for cid in node.children:
            child = session.nodes.get(cid)
            if child and child.result_file:
                file_list.append(f"  - {child.title} → {child.result_file}")
        files_info = "\n".join(file_list) if file_list else "  (no files)"

        system += (
            "\n\n## Important: Compose Phase\n"
            "All your child tasks are complete. Their results are in the \"Child Task Results\" context section.\n"
            "Your goal now is: **complete your own task based on the child task results**.\n\n"
            "### Child Task File List\n"
            f"{files_info}\n\n"
            "### Output Principles (must strictly follow)\n"
            "1. **Do NOT call decompose**\n"
            "2. **Do NOT copy-paste large chunks of child task text** — child results are saved as separate files that users can view directly\n"
            "3. **Reference files**: In your answer, use the format `see xxx.md` to reference child task files — use filename only, no path\n"
            "4. Your answer should demonstrate independent thinking: extract key conclusions, make judgments, add your own analysis\n"
            "5. If you are the root node, your output is the final deliverable — it should be concise and well-structured, with readers getting details from referenced files\n\n"
            "### Reference Format Example\n"
            "Correct: \"Based on research, we recommend the Redis cluster approach (see Tech_Selection.md). The key reason is...\"\n"
            "Wrong: Copying hundreds of words from child task results verbatim\n"
        )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Process this task: {node.title}\n\n{node.instruction}"},
    ]


def _preview(args: dict) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s[:120] + "..." if len(s) > 120 else s
