"""Shell execution tool — ported from nanobot."""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from .base import Tool


class ExecTool(Tool):
    """Execute shell commands with safety guards."""

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",
            r"\bdel\s+/[fq]\b",
            r"\brmdir\s+/s\b",
            r"(?:^|[;&|]\s*)format\b",
            r"\b(mkfs|diskpart)\b",
            r"\bdd\s+if=",
            r">\s*/dev/sd",
            r"\b(shutdown|reboot|poweroff)\b",
            r":\(\)\s*\{.*\};\s*:",
        ]
        self.restrict_to_workspace = restrict_to_workspace

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return the output. Use for running scripts, installing dependencies, data processing, etc. Use with caution."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute",
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for the command (optional)",
                },
            },
            "required": ["command"],
        }

    async def execute(
        self, command: str, working_dir: str | None = None, **kw: Any
    ) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass
                return f"Error: Command timed out after {self.timeout} seconds"

            parts: list[str] = []
            if stdout:
                parts.append(stdout.decode("utf-8", errors="replace"))
            if stderr:
                t = stderr.decode("utf-8", errors="replace").strip()
                if t:
                    parts.append(f"STDERR:\n{t}")
            if process.returncode != 0:
                parts.append(f"\nExit code: {process.returncode}")

            result = "\n".join(parts) if parts else "(no output)"
            max_len = 10000
            if len(result) > max_len:
                result = (
                    result[:max_len]
                    + f"\n... (truncated, {len(result) - max_len} more chars)"
                )
            return result
        except Exception as e:
            return f"Error executing command: {e}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        lower = command.strip().lower()
        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"
        if self.restrict_to_workspace:
            if "..\\" in command or "../" in command:
                return "Error: Command blocked (path traversal detected)"
            cwd_path = Path(cwd).resolve()
            for raw in self._extract_absolute_paths(command):
                try:
                    p = Path(raw.strip()).resolve()
                except Exception:
                    continue
                if p.is_absolute() and cwd_path not in p.parents and p != cwd_path:
                    return "Error: Command blocked (path outside working dir)"
        return None

    @staticmethod
    def _extract_absolute_paths(command: str) -> list[str]:
        win = re.findall(r"[A-Za-z]:\\[^\s\"'|><;]+", command)
        posix = re.findall(r"(?:^|[\s|>])(/[^\s\"'>]+)", command)
        return win + posix
