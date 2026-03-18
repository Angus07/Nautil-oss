import { useCallback, useState } from "react";
import { useNautil } from "./hooks/useNautilSocket";
import TopBar from "./components/TopBar";
import DAGCanvas from "./components/DAGCanvas";
import NodeInspector from "./components/NodeInspector";
import EventStream from "./components/EventStream";

export default function App() {
  const {
    nodes,
    edges,
    events,
    sessionId,
    sessionStatus,
    submitProblem,
    pauseNode,
    retryNode,
    sendFeedback,
    pauseSession,
    resumeSession,
  } = useNautil();

  const handleDownload = useCallback(() => {
    if (!sessionId) return;
    window.open(`/api/sessions/${sessionId}/download`, "_blank");
  }, [sessionId]);

  const [selectedId, setSelectedId] = useState<string | null>(null);

  const selectedNode = selectedId ? nodes[selectedId] ?? null : null;

  const handleSelectNode = useCallback((id: string) => {
    setSelectedId((prev) => (prev === id ? null : id));
  }, []);

  const handleEventClick = useCallback((nodeId: string) => {
    setSelectedId(nodeId);
  }, []);

  const hasNodes = Object.keys(nodes).length > 0;

  return (
    <div className="h-screen w-screen flex flex-col bg-[#0a0f1a] text-slate-100 overflow-hidden">
      <TopBar
        onSubmit={submitProblem}
        sessionStatus={sessionStatus}
        nodes={nodes}
        onPause={pauseSession}
        onResume={resumeSession}
        onDownload={handleDownload}
      />

      <div className="flex-1 relative overflow-hidden">
        {hasNodes ? (
          <DAGCanvas
            nautilNodes={nodes}
            nautilEdges={edges}
            onSelectNode={handleSelectNode}
          />
        ) : (
          <EmptyState />
        )}

        {selectedNode && (
          <div className="absolute right-4 top-4 bottom-16 z-50">
            <NodeInspector
              node={selectedNode}
              events={events}
              onClose={() => setSelectedId(null)}
              onPause={pauseNode}
              onRetry={retryNode}
              onFeedback={sendFeedback}
            />
          </div>
        )}

        {sessionStatus === "draft_ready" && (
          <div className="absolute bottom-20 left-1/2 -translate-x-1/2 z-40 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="flex items-center gap-4 px-6 py-3.5 rounded-2xl bg-slate-900/90 border border-amber-500/30 backdrop-blur-lg shadow-lg shadow-amber-500/5">
              <div className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              <span className="text-sm text-slate-200">
                Draft planning complete. Please review all nodes before approving execution.
              </span>
              <button
                onClick={resumeSession}
                className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-xl text-sm font-semibold text-white transition-colors cursor-pointer"
              >
                Approve Execution
              </button>
            </div>
          </div>
        )}
      </div>

      <EventStream events={events} onClickEvent={handleEventClick} />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center gap-4 select-none">
      <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-600/20 to-purple-600/20 border border-slate-800 flex items-center justify-center">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" className="text-slate-600">
          <circle cx="12" cy="6" r="2.5" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="6" cy="17" r="2.5" stroke="currentColor" strokeWidth="1.5" />
          <circle cx="18" cy="17" r="2.5" stroke="currentColor" strokeWidth="1.5" />
          <path d="M12 8.5V12M12 12L7.5 14.5M12 12L16.5 14.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </div>
      <div className="text-center">
        <h2 className="text-lg font-semibold text-slate-400">Nautil Problem-Solving Console</h2>
        <p className="text-sm text-slate-600 mt-1">Enter a problem and watch AI recursively decompose and solve it</p>
      </div>
    </div>
  );
}
