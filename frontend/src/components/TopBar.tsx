import { useState, type FormEvent } from "react";
import { Send, Loader2, Pause, Play, RotateCcw, Zap, Download, ShieldCheck, ShieldOff, ChevronDown } from "lucide-react";
import type { NautilNode } from "../types";

interface Props {
  onSubmit: (problem: string, verifyMode: boolean, maxDepth: number, maxConcurrency: number, maxChildren: number) => void;
  sessionStatus: string;
  nodes: Record<string, NautilNode>;
  onPause: () => void;
  onResume: () => void;
  onDownload: () => void;
}

export default function TopBar({ onSubmit, sessionStatus, nodes, onPause, onResume, onDownload }: Props) {
  const [input, setInput] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [verifyMode, setVerifyMode] = useState(false);
  const [maxDepth, setMaxDepth] = useState(2);
  const [maxConcurrency, setMaxConcurrency] = useState(2);
  const [maxChildren, setMaxChildren] = useState(5);

  const nodeList = Object.values(nodes);
  const total = nodeList.length;
  const passed = nodeList.filter((n) => n.status === "passed").length;
  const active = nodeList.filter((n) =>
    ["executing", "decomposing", "verifying"].includes(n.status),
  ).length;
  const failed = nodeList.filter((n) => n.status === "failed").length;
  const pct = total > 0 ? Math.round((passed / total) * 100) : 0;

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSubmit(input.trim(), verifyMode, maxDepth, maxConcurrency, maxChildren);
    setSubmitted(true);
  };

  const isRunning = sessionStatus === "running";
  const isDraftReady = sessionStatus === "draft_ready";
  const isDone = sessionStatus === "completed" || sessionStatus === "failed";

  return (
    <header className="flex-shrink-0 border-b border-slate-800 bg-slate-950/80 backdrop-blur-md">
      <div className="px-5 py-3 flex items-center gap-4">
        {/* Logo */}
        <div className="flex items-center gap-2 mr-2 flex-shrink-0">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <Zap size={18} className="text-white" />
          </div>
          <span className="text-lg font-bold text-slate-100 tracking-tight font-display">
            Nautil
          </span>
        </div>

        {/* Input */}
        {!submitted ? (
          <form onSubmit={handleSubmit} className="flex-1 flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Enter a complex problem and watch AI solve it recursively..."
              className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/30 transition-colors"
            />
            <button
              type="button"
              onClick={() => setVerifyMode((v) => !v)}
              title={verifyMode ? "Verify mode: verify each result" : "Fast mode: skip verification"}
              className={`flex items-center gap-1.5 px-3 py-2.5 rounded-lg text-xs font-medium border transition-colors cursor-pointer flex-shrink-0 ${
                verifyMode
                  ? "bg-amber-600/15 border-amber-500/30 text-amber-400 hover:bg-amber-600/25"
                  : "bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-700"
              }`}
            >
              {verifyMode ? <ShieldCheck size={13} /> : <ShieldOff size={13} />}
              {verifyMode ? "Verify" : "Fast"}
            </button>
            <ConfigSelect label="Depth" value={maxDepth} options={[1,2,3,4]} onChange={setMaxDepth} />
            <ConfigSelect label="Concur" value={maxConcurrency} options={[1,2,3,4,5,6,7,8,9,10]} onChange={setMaxConcurrency} />
            <ConfigSelect label="Branch" value={maxChildren} options={[3,4,5,6,7,8,9,10]} onChange={setMaxChildren} />
            <button
              type="submit"
              disabled={!input.trim()}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white flex items-center gap-2 transition-colors cursor-pointer"
            >
              <Send size={14} />
              Solve
            </button>
          </form>
        ) : (
          <div className="flex-1 flex items-center gap-3 min-w-0">
            <div className="text-sm text-slate-300 truncate flex-1 bg-slate-900/60 rounded-lg px-3 py-2 border border-slate-800">
              {input}
            </div>
            {isDone && (
              <>
                <button
                  onClick={onDownload}
                  className="px-3 py-2 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 rounded-lg text-xs text-emerald-400 flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <Download size={12} /> Download
                </button>
                <button
                  onClick={() => { setSubmitted(false); setInput(""); }}
                  className="px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-xs text-slate-300 flex items-center gap-1.5 transition-colors cursor-pointer"
                >
                  <RotateCcw size={12} /> New
                </button>
              </>
            )}
          </div>
        )}

        {/* Stats */}
        {total > 0 && (
          <div className="flex items-center gap-4 flex-shrink-0 text-xs">
            <div className="flex items-center gap-3">
              <Stat label="Nodes" value={total} color="text-slate-300" />
              <Stat label="Done" value={passed} color="text-emerald-400" />
              <Stat label="Active" value={active} color="text-blue-400" />
              {failed > 0 && <Stat label="Failed" value={failed} color="text-red-400" />}
            </div>

            <div className="flex items-center gap-2">
              <div className="w-20 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${pct}%`,
                    background: isDone && sessionStatus === "completed"
                      ? "#22c55e"
                      : isDone && sessionStatus === "failed"
                        ? "#ef4444"
                        : "#3b82f6",
                  }}
                />
              </div>
              <span className="text-slate-400 w-8 text-right">{pct}%</span>
            </div>

            {isDraftReady && (
              <>
                <span className="text-amber-400 text-xs font-medium">Draft complete, please review</span>
                <button
                  onClick={onResume}
                  className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 rounded-lg text-emerald-400 font-medium transition-colors cursor-pointer"
                >
                  <Play size={12} />
                  <span>Approve</span>
                </button>
              </>
            )}
            {isRunning && (
              <>
                <button
                  onClick={onPause}
                  className="flex items-center gap-1 px-2.5 py-1.5 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-500/30 rounded-lg text-amber-400 transition-colors cursor-pointer"
                >
                  <Pause size={12} />
                  <span>Pause</span>
                </button>
                <div className="flex items-center gap-1 text-blue-400">
                  <Loader2 size={12} className="animate-spin" />
                  <span>Solving</span>
                </div>
              </>
            )}
            {sessionStatus === "paused" && (
              <button
                onClick={onResume}
                className="flex items-center gap-1 px-2.5 py-1.5 bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 rounded-lg text-blue-400 transition-colors cursor-pointer"
              >
                <Play size={12} />
                <span>Resume</span>
              </button>
            )}
            {sessionStatus === "completed" && (
              <span className="text-emerald-400 font-medium">Completed</span>
            )}
            {sessionStatus === "failed" && (
              <span className="text-red-400 font-medium">Failed</span>
            )}
          </div>
        )}
      </div>
    </header>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-1">
      <span className="text-slate-500">{label}</span>
      <span className={`font-mono font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function ConfigSelect({ label, value, options, onChange }: {
  label: string;
  value: number;
  options: number[];
  onChange: (v: number) => void;
}) {
  return (
    <div className="relative flex items-center gap-1.5 flex-shrink-0">
      <span className="text-[11px] text-slate-500">{label}</span>
      <div className="relative">
        <select
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="appearance-none bg-slate-800 border border-slate-700 rounded-lg pl-2.5 pr-6 py-2 text-xs font-mono font-semibold text-slate-200 cursor-pointer hover:border-slate-600 focus:outline-none focus:border-blue-500 transition-colors"
        >
          {options.map((o) => (
            <option key={o} value={o}>{o}</option>
          ))}
        </select>
        <ChevronDown size={11} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none" />
      </div>
    </div>
  );
}
