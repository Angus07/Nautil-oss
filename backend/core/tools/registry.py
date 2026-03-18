"""Tool registry — adapted from nanobot."""
from __future__ import annotations
from typing import Any
from .base import Tool

_HINT = "\n\n[Please analyze the error and try an alternative approach.]"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get_definitions(self) -> list[dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]

    async def execute(self, name: str, params: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            avail = ", ".join(self._tools.keys())
            return f"Error: Tool '{name}' not found. Available: {avail}"
        try:
            result = await tool.execute(**params)
            if isinstance(result, str) and result.startswith("Error"):
                return result + _HINT
            return result
        except Exception as exc:
            return f"Error executing {name}: {exc}" + _HINT

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
