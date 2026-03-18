import { useEffect, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  BackgroundVariant,
  MarkerType,
} from "reactflow";
import dagre from "@dagrejs/dagre";
import "reactflow/dist/style.css";

import { NautilNodeComponent } from "./NautilNode";
import type { NautilNode, NautilEdge, NodeStatus } from "../types";
import { STATUS_META } from "../types";

const nodeTypes = { nautil: NautilNodeComponent };

const NODE_W = 200;
const NODE_H = 80;

function layoutDAG(
  nautilNodes: Record<string, NautilNode>,
  nautilEdges: NautilEdge[],
  onSelect: (id: string) => void,
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 90, marginx: 40, marginy: 40 });

  const ids = Object.keys(nautilNodes);
  ids.forEach((id) => g.setNode(id, { width: NODE_W, height: NODE_H }));

  nautilEdges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  const nodes: Node[] = ids.map((id) => {
    const n = nautilNodes[id];
    const pos = g.node(id);
    return {
      id,
      type: "nautil",
      position: { x: (pos?.x ?? 0) - NODE_W / 2, y: (pos?.y ?? 0) - NODE_H / 2 },
      data: {
        title: n.title,
        status: n.status,
        is_leaf: n.is_leaf,
        retry_count: n.retry_count,
        depth: n.depth,
        onSelect,
        nodeId: id,
      },
    };
  });

  const edges: Edge[] = nautilEdges.map((e) => {
    const isParent = e.type === "parent";
    const srcStatus = nautilNodes[e.source]?.status as NodeStatus;
    const tgtStatus = nautilNodes[e.target]?.status as NodeStatus;
    const isEscalating = tgtStatus === "escalating" || tgtStatus === "failed";
    const isFlowing = srcStatus === "passed" && tgtStatus !== "passed";

    return {
      id: e.id,
      source: e.source,
      target: e.target,
      animated: !isParent && (isFlowing || isEscalating),
      style: {
        stroke: isEscalating
          ? "#f97316"
          : isParent
            ? "#64748b"
            : isFlowing
              ? "#3b82f6"
              : "#475569",
        strokeWidth: isParent ? 1 : isEscalating || isFlowing ? 2 : 1.5,
        strokeDasharray: isParent ? "6 3" : undefined,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: isEscalating
          ? "#f97316"
          : isParent
            ? "#64748b"
            : isFlowing
              ? "#3b82f6"
              : "#475569",
        width: isParent ? 12 : 16,
        height: isParent ? 12 : 16,
      },
    };
  });

  return { nodes, edges };
}

interface Props {
  nautilNodes: Record<string, NautilNode>;
  nautilEdges: NautilEdge[];
  onSelectNode: (id: string) => void;
}

export default function DAGCanvas({ nautilNodes, nautilEdges, onSelectNode }: Props) {
  const layout = useMemo(
    () => layoutDAG(nautilNodes, nautilEdges, onSelectNode),
    [nautilNodes, nautilEdges, onSelectNode],
  );

  const [rfNodes, setRfNodes, onNodesChange] = useNodesState([]);
  const [rfEdges, setRfEdges, onEdgesChange] = useEdgesState([]);

  useEffect(() => {
    setRfNodes(layout.nodes);
    setRfEdges(layout.edges);
  }, [layout, setRfNodes, setRfEdges]);

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.3, maxZoom: 1.2 }}
        proOptions={{ hideAttribution: true }}
        className="bg-transparent"
      >
        <Background variant={BackgroundVariant.Dots} color="#1e293b" gap={20} size={1} />
        <Controls
          className="!bg-slate-800/80 !border-slate-700 !rounded-lg !shadow-lg [&>button]:!bg-slate-800 [&>button]:!border-slate-700 [&>button]:!text-slate-300 [&>button:hover]:!bg-slate-700"
        />
        <MiniMap
          nodeColor={(n) => {
            const st = (n.data as { status: string }).status as NodeStatus;
            return STATUS_META[st]?.color ?? "#475569";
          }}
          className="!bg-slate-900/80 !border-slate-700 !rounded-lg"
          maskColor="rgba(15,23,42,.7)"
        />
      </ReactFlow>
    </div>
  );
}
