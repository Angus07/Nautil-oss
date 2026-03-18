"""Three structural tools: decompose, submit_result, escalate.

These are created per-node and share a `signal` dict with the agent loop.
When a structural tool fires, it sets signal["type"] which causes the loop
to exit and hand control back to the engine.
"""
from __future__ import annotations
from typing import Any
from .base import Tool


class DecomposeTool(Tool):
    def __init__(self, signal: dict):
        self._signal = signal

    @property
    def name(self):
        return "decompose"

    @property
    def description(self):
        return (
            "Decompose the current problem into multiple sub-tasks. Call this when the problem is too complex to solve directly. "
            "Each sub-task has a title and instruction."
        )

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "subtasks": {
                    "type": "array",
                    "description": "List of independent sub-tasks to be executed in parallel",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Sub-task title"},
                            "instruction": {"type": "string", "description": "Detailed instruction"},
                        },
                        "required": ["title", "instruction"],
                    },
                },
            },
            "required": ["subtasks"],
        }

    async def execute(self, *, subtasks: list[dict[str, Any]], **_kw: Any) -> str:
        self._signal["type"] = "decomposed"
        self._signal["data"] = subtasks
        return f"Decomposed into {len(subtasks)} sub-tasks."


class SubmitResultTool(Tool):
    def __init__(self, signal: dict):
        self._signal = signal

    @property
    def name(self):
        return "submit_result"

    @property
    def description(self):
        return "Submit the final result of the current node. The system will automatically verify result quality."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "The complete result of the task"},
            },
            "required": ["result"],
        }

    async def execute(self, *, result: str, **_kw: Any) -> str:
        self._signal["type"] = "completed"
        self._signal["data"] = result
        return "Result submitted, awaiting verification."


class EscalateTool(Tool):
    def __init__(self, signal: dict):
        self._signal = signal

    @property
    def name(self):
        return "escalate"

    @property
    def description(self):
        return "Escalate to the parent node when the current problem cannot be solved under existing conditions. Explain the reason and approaches already tried."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for failure and approaches already attempted",
                },
            },
            "required": ["reason"],
        }

    async def execute(self, *, reason: str, **_kw: Any) -> str:
        self._signal["type"] = "escalated"
        self._signal["data"] = reason
        return "Escalated to parent node for handling."
