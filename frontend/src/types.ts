export type NodeStatus =
  | "pending"
  | "ready"
  | "decomposing"
  | "executing"
  | "verifying"
  | "passed"
  | "failed"
  | "escalating"
  | "waiting_human"
  | "paused";

export interface NautilNode {
  id: string;
  title: string;
  parent_id: string | null;
  children: string[];
  status: NodeStatus;
  delta_state: string;
  instruction: string;
  result: string | null;
  verify_result: string | null;
  verify_passed: boolean | null;
  error_message: string | null;
  result_file: string | null;
  context_log: { type: string; tool?: string; content?: string; timestamp?: string }[];
  retry_count: number;
  max_retries: number;
  is_leaf: boolean;
  depth: number;
  created_at: string;
}

export interface NautilEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
}

export interface NautilEvent {
  timestamp: string;
  message: string;
  node_id: string | null;
  level: "info" | "warning" | "error" | "success";
}

export interface SessionState {
  id: string;
  problem: string;
  understanding: string | null;
  confirmed: boolean;
  nodes: Record<string, NautilNode>;
  edges: NautilEdge[];
  root_id: string | null;
  status: string;
  events: NautilEvent[];
  created_at: string;
}

export interface WSMessage {
  type: string;
  data: Record<string, unknown>;
}

export const STATUS_META: Record<
  NodeStatus,
  { label: string; color: string; bg: string; border: string; pulse?: boolean }
> = {
  pending:       { label: "Pending",     color: "#71717a", bg: "rgba(113,113,122,.12)", border: "#3f3f46" },
  ready:         { label: "Ready",       color: "#38bdf8", bg: "rgba(56,189,248,.12)",  border: "#0ea5e9", pulse: true },
  decomposing:   { label: "Decomposing", color: "#a78bfa", bg: "rgba(167,139,250,.12)", border: "#8b5cf6", pulse: true },
  executing:     { label: "Executing",   color: "#3b82f6", bg: "rgba(59,130,246,.12)",  border: "#2563eb", pulse: true },
  verifying:     { label: "Verifying",   color: "#fbbf24", bg: "rgba(251,191,36,.12)",  border: "#f59e0b", pulse: true },
  passed:        { label: "Passed",      color: "#22c55e", bg: "rgba(34,197,94,.12)",   border: "#16a34a" },
  failed:        { label: "Failed",      color: "#ef4444", bg: "rgba(239,68,68,.12)",   border: "#dc2626" },
  escalating:    { label: "Escalating",  color: "#f97316", bg: "rgba(249,115,22,.12)",  border: "#ea580c", pulse: true },
  waiting_human: { label: "Needs Human", color: "#fb923c", bg: "rgba(251,146,60,.15)",  border: "#f97316", pulse: true },
  paused:        { label: "Paused",      color: "#94a3b8", bg: "rgba(148,163,184,.12)", border: "#64748b" },
};
