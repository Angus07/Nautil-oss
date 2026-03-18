import { useCallback, useEffect, useRef, useState } from "react";
import type { NautilNode, NautilEdge, NautilEvent, SessionState } from "../types";

const API = "";
const WS_URL = `ws://${window.location.host}`;

export function useNautil() {
  const [nodes, setNodes] = useState<Record<string, NautilNode>>({});
  const [edges, setEdges] = useState<NautilEdge[]>([]);
  const [events, setEvents] = useState<NautilEvent[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionStatus, setSessionStatus] = useState<string>("idle");
  const wsRef = useRef<WebSocket | null>(null);

  const handleMsg = useCallback((raw: MessageEvent) => {
    const msg = JSON.parse(raw.data);
    const { type, data } = msg as { type: string; data: unknown };

    switch (type) {
      case "session_state": {
        const s = data as unknown as SessionState;
        setNodes(s.nodes);
        setEdges(s.edges);
        setEvents(s.events);
        setSessionStatus(s.status);
        break;
      }
      case "node_created":
      case "node_updated":
        setNodes((prev) => ({ ...prev, [(data as NautilNode).id]: data as NautilNode }));
        break;
      case "edge_created":
        setEdges((prev) => {
          const e = data as NautilEdge;
          if (prev.some((x) => x.id === e.id)) return prev;
          return [...prev, e];
        });
        break;
      case "node_log": {
        const { node_id, entry } = data as { node_id: string; entry: NautilNode["context_log"][0] };
        setNodes((prev) => {
          const n = prev[node_id];
          if (!n) return prev;
          return { ...prev, [node_id]: { ...n, context_log: [...n.context_log, entry] } };
        });
        break;
      }
      case "event":
        setEvents((prev) => [...prev, data as NautilEvent]);
        break;
      case "session_update":
        setSessionStatus((data as { status: string; }).status);
        break;
    }
  }, []);

  const connect = useCallback(
    (sid: string) => {
      if (wsRef.current) wsRef.current.close();
      const ws = new WebSocket(`${WS_URL}/ws/${sid}`);
      ws.onmessage = handleMsg;
      ws.onclose = () => {
        wsRef.current = null;
      };
      wsRef.current = ws;
    },
    [handleMsg],
  );

  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  const submitProblem = useCallback(
    async (problem: string, verifyMode: boolean = false, maxDepth: number = 2, maxConcurrency: number = 2, maxChildren: number = 5) => {
      const res = await fetch(`${API}/api/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          problem,
          verify_mode: verifyMode,
          max_depth: maxDepth,
          max_concurrency: maxConcurrency,
          max_children: maxChildren,
        }),
      });
      const { session_id } = await res.json();
      setSessionId(session_id);
      setNodes({});
      setEdges([]);
      setEvents([]);
      setSessionStatus("created");

      connect(session_id);

      await new Promise((r) => setTimeout(r, 300));

      await fetch(`${API}/api/sessions/${session_id}/start`, { method: "POST" });
      setSessionStatus("running");
    },
    [connect],
  );

  const pauseNode = useCallback(
    async (nid: string) => {
      if (!sessionId) return;
      await fetch(`${API}/api/sessions/${sessionId}/nodes/${nid}/pause`, { method: "POST" });
    },
    [sessionId],
  );

  const retryNode = useCallback(
    async (nid: string) => {
      if (!sessionId) return;
      await fetch(`${API}/api/sessions/${sessionId}/nodes/${nid}/retry`, { method: "POST" });
    },
    [sessionId],
  );

  const sendFeedback = useCallback(
    async (nid: string, feedback: string) => {
      if (!sessionId) return;
      await fetch(`${API}/api/sessions/${sessionId}/nodes/${nid}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback }),
      });
    },
    [sessionId],
  );

  const pauseSession = useCallback(async () => {
    if (!sessionId) return;
    await fetch(`${API}/api/sessions/${sessionId}/pause`, { method: "POST" });
  }, [sessionId]);

  const resumeSession = useCallback(async () => {
    if (!sessionId) return;
    await fetch(`${API}/api/sessions/${sessionId}/resume`, { method: "POST" });
  }, [sessionId]);

  return {
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
  };
}
