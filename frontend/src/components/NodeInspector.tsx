import { useState, useEffect, useRef } from "react";
import {
  X,
  FileText,
  ClipboardCheck,
  ScrollText,
  Pause,
  RotateCcw,
  MessageSquare,
  Send,
} from "lucide-react";
import type { NautilNode, NautilEvent } from "../types";
import { STATUS_META } from "../types";

type Tab = "context" | "result" | "log";

interface Props {
  node: NautilNode;
  events: NautilEvent[];
  onClose: () => void;
  onPause: (id: string) => void;
  onRetry: (id: string) => void;
  onFeedback: (id: string, fb: string) => void;
}

export default function NodeInspector({ node, events, onClose, onPause, onRetry, onFeedback }: Props) {
  const [tab, setTab] = useState<Tab>("context");
  const [feedback, setFeedback] = useState("");

  const meta = STATUS_META[node.status];
  const nodeEvents = events.filter((e) => e.node_id === node.id);

  const canPause = ["executing", "decomposing", "pending"].includes(node.status);
  const canRetry = ["failed", "paused"].includes(node.status);
  const needsHuman = node.status === "waiting_human";
  const canFeedback = needsHuman || node.status === "paused";

  const tabs: { key: Tab; label: string; icon: typeof FileText }[] = [
    { key: "context", label: "Context", icon: FileText },
    { key: "result", label: "Result", icon: ClipboardCheck },
    { key: "log", label: "Log", icon: ScrollText },
  ];

  return (
    <div className="w-[380px] h-full rounded-xl border border-slate-700/80 bg-slate-950/95 backdrop-blur-xl flex flex-col overflow-hidden shadow-2xl shadow-black/40">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-100 truncate">{node.title}</div>
          <div className="flex items-center gap-2 mt-1">
            <span
              className="text-[10px] font-medium px-1.5 py-0.5 rounded-full"
              style={{ background: `${meta.color}20`, color: meta.color }}
            >
              {meta.label}
            </span>
            <span className="text-[10px] text-slate-500">
              Depth {node.depth} · {node.is_leaf ? "Leaf" : "Branch"}
            </span>
          </div>
        </div>
        <button onClick={onClose} className="p-1 hover:bg-slate-800 rounded transition-colors cursor-pointer">
          <X size={16} className="text-slate-400" />
        </button>
      </div>

      {/* Actions */}
      <div className="px-4 py-2 border-b border-slate-800 flex gap-2">
        {canPause && (
          <ActionBtn icon={Pause} label="Pause" onClick={() => onPause(node.id)} />
        )}
        {canRetry && (
          <ActionBtn icon={RotateCcw} label="Retry" onClick={() => onRetry(node.id)} color="text-blue-400" />
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800">
        {tabs.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2.5 text-xs font-medium transition-colors cursor-pointer ${
              tab === key
                ? "text-blue-400 border-b-2 border-blue-400 bg-blue-500/5"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 text-sm">
        {tab === "context" && <ContextTab node={node} />}
        {tab === "result" && <ResultTab node={node} />}
        {tab === "log" && <LogTab events={nodeEvents} />}
      </div>

      {/* Feedback input */}
      {canFeedback && (
        <div className={`p-3 border-t ${needsHuman ? "border-orange-500/30 bg-orange-500/5" : "border-blue-500/30 bg-blue-500/5"}`}>
          <div className={`text-xs font-medium mb-2 flex items-center gap-1 ${needsHuman ? "text-orange-400" : "text-blue-400"}`}>
            <MessageSquare size={12} />
            {needsHuman ? "This node needs your help" : "Add instructions or modify requirements"}
          </div>
          <div className="flex gap-2">
            <input
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder={needsHuman ? "Enter feedback..." : "Add instructions, e.g.: focus on..."}
              className={`flex-1 bg-slate-900 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 placeholder:text-slate-600 focus:outline-none ${needsHuman ? "focus:border-orange-500" : "focus:border-blue-500"}`}
              onKeyDown={(e) => {
                if (e.key === "Enter" && feedback.trim()) {
                  onFeedback(node.id, feedback.trim());
                  setFeedback("");
                }
              }}
            />
            <button
              onClick={() => {
                if (feedback.trim()) {
                  onFeedback(node.id, feedback.trim());
                  setFeedback("");
                }
              }}
              className={`p-1.5 rounded text-white transition-colors cursor-pointer ${needsHuman ? "bg-orange-600 hover:bg-orange-500" : "bg-blue-600 hover:bg-blue-500"}`}
            >
              <Send size={12} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ActionBtn({
  icon: Icon,
  label,
  onClick,
  color = "text-slate-300",
}: {
  icon: typeof Pause;
  label: string;
  onClick: () => void;
  color?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1 px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 rounded text-xs font-medium transition-colors cursor-pointer ${color}`}
    >
      <Icon size={12} />
      {label}
    </button>
  );
}

function ContextTab({ node }: { node: NautilNode }) {
  const logEndRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [node.context_log.length]);

  return (
    <div className="space-y-4">
      <Section title="Instruction">
        <p className="text-slate-300 whitespace-pre-wrap">{node.instruction || "—"}</p>
      </Section>
      <Section title="Delta State (ΔState)">
        <p className="text-slate-300 whitespace-pre-wrap">{node.delta_state || "(none)"}</p>
      </Section>
      {node.context_log && node.context_log.length > 0 && (
        <Section title="Execution Timeline">
          <div className="space-y-1.5">
            {node.context_log.map((entry, i) => (
              <div key={i} className="flex gap-2 text-xs">
                <span className="text-slate-600 font-mono flex-shrink-0 w-14">{entry.timestamp || ""}</span>
                <div className="min-w-0 flex-1">
                  {entry.type === "tool_call" && (
                    <div>
                      <span className="text-blue-400 font-medium">▶ {entry.tool}</span>
                      <div className="text-slate-500 truncate mt-0.5">{entry.content}</div>
                    </div>
                  )}
                  {entry.type === "tool_result" && (
                    <div>
                      <span className="text-emerald-400 font-medium">◀ {entry.tool}</span>
                      <div className="text-slate-500 line-clamp-3 mt-0.5 whitespace-pre-wrap">{entry.content}</div>
                    </div>
                  )}
                  {entry.type === "assistant" && (
                    <div className="text-slate-300 whitespace-pre-wrap line-clamp-4">
                      <span className="text-purple-400 font-medium">💭 </span>{entry.content}
                    </div>
                  )}
                  {entry.type === "error" && (
                    <div className="text-red-400 whitespace-pre-wrap line-clamp-3">
                      <span className="font-medium">✗ Error: </span>{entry.content}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </Section>
      )}
    </div>
  );
}

function ResultTab({ node }: { node: NautilNode }) {
  return (
    <div className="space-y-4">
      {node.error_message && (
        <Section title="Error">
          <div className="text-xs text-red-400 whitespace-pre-wrap bg-red-500/5 border border-red-500/20 rounded-lg p-3 font-mono leading-relaxed max-h-60 overflow-y-auto">
            {node.error_message}
          </div>
        </Section>
      )}
      <Section title="Result">
        {node.result ? (
          <div className="text-slate-300 whitespace-pre-wrap text-xs leading-relaxed bg-slate-900/50 rounded-lg p-3 border border-slate-800">
            {node.result}
          </div>
        ) : (
          <p className="text-slate-500 italic">No result yet</p>
        )}
      </Section>
      {node.verify_result && (
        <Section title="Verification">
          <div
            className={`text-xs px-3 py-2 rounded-lg border ${
              node.verify_passed
                ? "bg-emerald-500/5 border-emerald-500/20 text-emerald-400"
                : "bg-red-500/5 border-red-500/20 text-red-400"
            }`}
          >
            {node.verify_result}
          </div>
        </Section>
      )}
    </div>
  );
}

function LogTab({ events }: { events: NautilEvent[] }) {
  if (!events.length) {
    return <p className="text-slate-500 italic text-xs">No logs yet</p>;
  }
  return (
    <div className="space-y-1">
      {events.map((ev, i) => (
        <div key={i} className="flex gap-2 text-xs py-1">
          <span className="text-slate-600 font-mono flex-shrink-0">{ev.timestamp}</span>
          <span
            className={
              ev.level === "error"
                ? "text-red-400"
                : ev.level === "warning"
                  ? "text-orange-400"
                  : ev.level === "success"
                    ? "text-emerald-400"
                    : "text-slate-400"
            }
          >
            {ev.message}
          </span>
        </div>
      ))}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
        {title}
      </h4>
      {children}
    </div>
  );
}
