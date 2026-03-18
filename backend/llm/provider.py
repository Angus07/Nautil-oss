"""LLM Provider: OpenAI-compatible (covers OpenAI / GLM / others) + Mock."""
from __future__ import annotations
import asyncio
import json
import os
import random
import uuid
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()


# ── data classes ──

@dataclass
class ToolCallRequest:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


# ── OpenAI-compatible provider ──

class OpenAIProvider:
    """Works with OpenAI, GLM (Z.AI), and any OpenAI-compatible endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
        self.model = model

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.7),
        }
        if tools:
            params["tools"] = tools
            params["tool_choice"] = "auto"

        max_retries = 5
        for attempt in range(max_retries):
            try:
                resp = await self.client.chat.completions.create(**params)
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    wait = 2 ** attempt + random.uniform(0, 1)
                    await asyncio.sleep(wait)
                    if attempt == max_retries - 1:
                        raise
                else:
                    raise

        msg = resp.choices[0].message

        tool_calls: list[ToolCallRequest] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                args = tc.function.arguments
                if isinstance(args, str):
                    args = json.loads(args)
                tool_calls.append(
                    ToolCallRequest(id=tc.id, name=tc.function.name, arguments=args)
                )

        return LLMResponse(content=msg.content, tool_calls=tool_calls)


# ── Mock provider ──

class MockProvider:
    """Simulates tool-calling LLM responses for the demo flow."""

    def __init__(self, problem: str = ""):
        self.problem = problem

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        await asyncio.sleep(random.uniform(1.0, 2.0))

        system = messages[0].get("content", "") if messages else ""
        title = _extract_title(system)

        fail_count = sum(
            1 for m in messages
            if m.get("role") == "tool" and "✗" in m.get("content", "")
        )

        if fail_count >= 2:
            return _tc("escalate", {
                "reason": "Multiple verification failures — fundamental issues with current approach, re-evaluation needed",
            })

        if fail_count > 0:
            await asyncio.sleep(random.uniform(0.8, 1.5))
            return _tc("submit_result", {
                "result": (
                    f"## {title} (improved)\n\n"
                    f"Implementation improved based on verification feedback:\n"
                    f"1. Fixed boundary condition handling\n"
                    f"2. Added exception handling logic\n"
                    f"3. Optimized data structures"
                ),
            })

        if _should_decompose(title, self.problem):
            return _tc("decompose", {
                "subtasks": _get_subtasks(title, self.problem),
            })

        return _tc("submit_result", {
            "result": (
                f"## {title}\n\n"
                f"Completed all work for {title}:\n"
                f"1. Completed core analysis and research\n"
                f"2. Produced structured result document\n"
                f"3. Key metrics met expectations"
            ),
        })


# ── mock helpers ──

def _extract_title(system: str) -> str:
    for line in system.split("\n"):
        if "Current node: " in line:
            return line.split("Current node: ", 1)[-1].strip()
    return ""


def _should_decompose(title: str, problem: str) -> bool:
    if not title or title == problem:
        return True
    if "Core Implementation" in title and "Module" not in title and "fix" not in title:
        return True
    return False


def _get_subtasks(title: str, problem: str) -> list[dict]:
    if not title or title == problem:
        return [
            {"title": "Analysis & Research", "instruction": f"Analyze the key elements and background of '{problem}'", "depends_on": []},
            {"title": "Solution Design", "instruction": f"Design the solution framework for '{problem}'", "depends_on": [0]},
            {"title": "Core Implementation", "instruction": f"Implement the core content for '{problem}'", "depends_on": [1]},
            {"title": "Summary & Output", "instruction": f"Integrate results and produce final output", "depends_on": [2]},
        ]
    if "Core Implementation" in title:
        return [
            {"title": "Module A: Foundation", "instruction": "Build foundational framework and data structures", "depends_on": []},
            {"title": "Module B: Core Logic", "instruction": "Implement core business logic", "depends_on": [0]},
            {"title": "Integration Verification", "instruction": "Integrate all modules and verify", "depends_on": [0, 1]},
        ]
    return []


def _tc(name: str, args: dict) -> LLMResponse:
    return LLMResponse(
        tool_calls=[ToolCallRequest(id=f"call_{uuid.uuid4().hex[:8]}", name=name, arguments=args)]
    )


# ── factory ──

def create_provider(problem: str = "") -> tuple[Any, bool]:
    """Return (provider, is_mock) based on env vars."""
    mode = os.getenv("LLM_PROVIDER", "mock")

    if mode == "openai":
        return OpenAIProvider(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        ), False

    if mode == "glm":
        return OpenAIProvider(
            api_key=os.getenv("GLM_API_KEY", ""),
            model=os.getenv("GLM_MODEL", "glm-4-plus"),
            base_url=os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/"),
        ), False

    return MockProvider(problem=problem), True
