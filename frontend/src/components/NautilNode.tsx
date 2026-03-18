import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Pause,
  Bell,
  GitBranch,
  Play,
  Search,
} from "lucide-react";
import { STATUS_META, type NodeStatus } from "../types";

interface NautilNodeData {
  title: string;
  status: NodeStatus;
  is_leaf: boolean;
  retry_count: number;
  depth: number;
  onSelect: (id: string) => void;
  nodeId: string;
}

const StatusIcon = ({ status }: { status: NodeStatus }) => {
  const size = 14;
  switch (status) {
    case "decomposing":
      return <GitBranch size={size} className="animate-pulse" />;
    case "executing":
      return <Play size={size} className="animate-pulse" />;
    case "verifying":
      return <Search size={size} className="animate-spin" style={{ animationDuration: "2s" }} />;
    case "passed":
      return <CheckCircle2 size={size} />;
    case "failed":
      return <XCircle size={size} />;
    case "escalating":
      return <AlertTriangle size={size} className="animate-bounce" />;
    case "waiting_human":
      return <Bell size={size} className="animate-pulse" />;
    case "paused":
      return <Pause size={size} />;
    default:
      return <Loader2 size={size} className="opacity-40" />;
  }
};

export const NautilNodeComponent = memo(({ data }: NodeProps<NautilNodeData>) => {
  const meta = STATUS_META[data.status];
  const isActive = ["decomposing", "executing", "verifying", "escalating"].includes(data.status);

  return (
    <div
      className="nautil-node cursor-pointer select-none"
      style={{
        background: meta.bg,
        borderColor: meta.border,
        borderWidth: 2,
        borderStyle: "solid",
        borderRadius: 12,
        padding: "10px 14px",
        minWidth: 160,
        maxWidth: 220,
        backdropFilter: "blur(8px)",
        boxShadow: isActive
          ? `0 0 20px ${meta.color}30, 0 0 40px ${meta.color}10`
          : "0 2px 8px rgba(0,0,0,.3)",
        transition: "all .25s ease",
        animation:
          data.status === "failed"
            ? "shake .4s ease-in-out"
            : meta.pulse
              ? "glow-pulse 2s ease-in-out infinite"
              : undefined,
      }}
      onClick={() => data.onSelect(data.nodeId)}
    >
      <Handle type="target" position={Position.Top} className="!bg-slate-600 !border-slate-500 !w-2 !h-2" />

      <div className="flex items-center gap-2 mb-1">
        <span style={{ color: meta.color }}>
          <StatusIcon status={data.status} />
        </span>
        <span
          className="text-xs font-medium px-1.5 py-0.5 rounded-full"
          style={{ background: `${meta.color}20`, color: meta.color }}
        >
          {meta.label}
        </span>
      </div>

      <div className="text-sm font-semibold text-slate-100 leading-tight line-clamp-2">
        {data.title}
      </div>

      {data.retry_count > 0 && (
        <div className="text-[10px] text-orange-400 mt-1">
          Retry #{data.retry_count}
        </div>
      )}

      {isActive && (
        <div className="mt-2 h-1 rounded-full bg-slate-700 overflow-hidden">
          <div
            className="h-full rounded-full animate-progress"
            style={{ background: meta.color }}
          />
        </div>
      )}

      <Handle type="source" position={Position.Bottom} className="!bg-slate-600 !border-slate-500 !w-2 !h-2" />
    </div>
  );
});

NautilNodeComponent.displayName = "NautilNode";
