from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
import uuid


class NodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    DECOMPOSING = "decomposing"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    PASSED = "passed"
    FAILED = "failed"
    ESCALATING = "escalating"
    WAITING_HUMAN = "waiting_human"
    PAUSED = "paused"


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class NodeData(BaseModel):
    id: str = Field(default_factory=_short_id)
    title: str
    parent_id: Optional[str] = None
    children: list[str] = Field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    delta_state: str = ""
    instruction: str = ""
    result: Optional[str] = None
    verify_result: Optional[str] = None
    verify_passed: Optional[bool] = None
    error_message: Optional[str] = None
    result_file: Optional[str] = None
    context_log: list[dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2
    restructure_count: int = 0
    is_leaf: bool = True
    depth: int = 0
    created_at: str = Field(default_factory=_now_iso)


class EventData(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    message: str
    node_id: Optional[str] = None
    level: str = "info"


class SessionData(BaseModel):
    id: str = Field(default_factory=_short_id)
    problem: str
    verify_mode: bool = False
    max_depth: int = 2
    max_concurrency: int = 2
    max_children: int = 5
    understanding: Optional[str] = None
    confirmed: bool = False
    nodes: dict[str, NodeData] = Field(default_factory=dict)
    edges: list[dict[str, str]] = Field(default_factory=list)
    root_id: Optional[str] = None
    status: str = "created"
    events: list[EventData] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now_iso)


class WSMessage(BaseModel):
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
