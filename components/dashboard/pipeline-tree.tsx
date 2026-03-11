"use client";

import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  type Node,
  type Edge,
  type NodeTypes,
  BaseEdge,
  EdgeLabelRenderer,
  getSmoothStepPath,
  type EdgeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import Dagre from "@dagrejs/dagre";
import { PipelineNode } from "./pipeline-node";

// ── Types ───────────────────────────────────────────────────────────────────

interface PipelineNodeData {
  step_id: string;
  step_number: string;
  name: string;
  description: string;
  module_path: string;
  function_name: string;
  inputs: string[];
  outputs: string[];
  parameters?: Record<string, unknown>;
  children?: PipelineNodeData[];
  branch_condition?: string | null;
  function_signature?: string | null;
  line_number?: number | null;
}

interface PipelineTreeProps {
  steps: PipelineNodeData[];
  entryPoint: string;
  section: "modeling" | "forecast";
}

// ── Constants ───────────────────────────────────────────────────────────────

const NODE_WIDTH = 320;
const CHILD_NODE_WIDTH = 280;
const NODE_HEIGHT_COLLAPSED = 80;
const NODE_HEIGHT_EXPANDED = 340;

// ── Custom edge ─────────────────────────────────────────────────────────────

function PipelineEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
    borderRadius: 12,
  });

  const isBranch = !!(data as Record<string, unknown>)?.branchLabel;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: isBranch ? "#f59e0b" : "#374151",
          strokeWidth: isBranch ? 2 : 1.5,
          strokeDasharray: isBranch ? "6 3" : undefined,
        }}
      />
      {isBranch && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
              pointerEvents: "all",
            }}
            className="px-2 py-1 rounded text-[10px] bg-amber-500/10 text-amber-400/80 border border-amber-500/20 max-w-[200px] text-center font-light leading-tight"
          >
            {(data as Record<string, unknown>).branchLabel as string}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

// ── Node & edge types ───────────────────────────────────────────────────────

const nodeTypes: NodeTypes = { pipeline: PipelineNode as unknown as NodeTypes[string] };
const edgeTypes = { pipeline: PipelineEdge };

// ── Dagre layout ────────────────────────────────────────────────────────────

function layoutGraph(
  nodes: Node[],
  edges: Edge[],
  expandedNodes: Set<string>,
): { nodes: Node[]; edges: Edge[] } {
  const g = new Dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  g.setGraph({
    rankdir: "TB",
    nodesep: 60,
    ranksep: 100,
    marginx: 40,
    marginy: 40,
  });

  for (const node of nodes) {
    const isChild = (node.data as Record<string, unknown>).isChild;
    const w = isChild ? CHILD_NODE_WIDTH : NODE_WIDTH;
    const h = expandedNodes.has(node.id)
      ? NODE_HEIGHT_EXPANDED
      : NODE_HEIGHT_COLLAPSED;
    g.setNode(node.id, { width: w, height: h });
  }

  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  Dagre.layout(g);

  const layoutedNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    const isChild = (node.data as Record<string, unknown>).isChild;
    const w = isChild ? CHILD_NODE_WIDTH : NODE_WIDTH;
    const h = expandedNodes.has(node.id)
      ? NODE_HEIGHT_EXPANDED
      : NODE_HEIGHT_COLLAPSED;
    return {
      ...node,
      position: {
        x: pos.x - w / 2,
        y: pos.y - h / 2,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}

// ── Data transformation ─────────────────────────────────────────────────────

function stepsToGraph(
  steps: PipelineNodeData[],
  section: "modeling" | "forecast",
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const sectionColor = section === "modeling" ? "blue" : "violet";

  // Track the "last output node" for sequential chaining
  let prevNodeId: string | null = null;

  for (const step of steps) {
    const nodeId = step.step_id;

    nodes.push({
      id: nodeId,
      type: "pipeline",
      position: { x: 0, y: 0 },
      data: {
        ...step,
        sectionColor,
        hasChildren: (step.children?.length ?? 0) > 0,
        hasBranch: !!step.branch_condition,
      },
    });

    // Connect from previous node
    if (prevNodeId) {
      const edgeData: Record<string, unknown> = {};
      // Check if the PREVIOUS node had a branch condition
      const prevStep = steps.find((s) => s.step_id === prevNodeId);
      if (prevStep?.branch_condition) {
        edgeData.branchLabel = prevStep.branch_condition;
      }
      edges.push({
        id: `e-${prevNodeId}-${nodeId}`,
        source: prevNodeId,
        target: nodeId,
        type: "pipeline",
        data: edgeData,
        markerEnd: { type: MarkerType.ArrowClosed, color: "#6b7280", width: 16, height: 16 },
      });
    }

    // If this step has children, add them as a sub-chain
    if (step.children && step.children.length > 0) {
      let prevChildId: string | null = nodeId;

      for (const child of step.children) {
        const childId = child.step_id;

        nodes.push({
          id: childId,
          type: "pipeline",
          position: { x: 0, y: 0 },
          data: {
            ...child,
            sectionColor,
            isChild: true,
            hasChildren: false,
            hasBranch: !!child.branch_condition,
          },
        });

        edges.push({
          id: `e-${prevChildId}-${childId}`,
          source: prevChildId!,
          target: childId,
          type: "pipeline",
          data: child.branch_condition
            ? { branchLabel: child.branch_condition }
            : {},
          markerEnd: { type: MarkerType.ArrowClosed, color: "#6b7280", width: 16, height: 16 },
        });

        prevChildId = childId;
      }

      // The chain continues from the last child
      prevNodeId = prevChildId;
    } else {
      prevNodeId = nodeId;
    }
  }

  return { nodes, edges };
}

// ── Main component ──────────────────────────────────────────────────────────

export function PipelineTreeGraph({
  steps,
  entryPoint,
  section,
}: PipelineTreeProps) {
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set());

  const toggleExpand = useCallback((nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) next.delete(nodeId);
      else next.add(nodeId);
      return next;
    });
  }, []);

  const { nodes: rawNodes, edges: rawEdges } = useMemo(
    () => stepsToGraph(steps, section),
    [steps, section],
  );

  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => layoutGraph(rawNodes, rawEdges, expandedNodes),
    [rawNodes, rawEdges, expandedNodes],
  );

  const nodesWithCallbacks = useMemo(
    () =>
      layoutedNodes.map((node) => ({
        ...node,
        data: {
          ...(node.data as Record<string, unknown>),
          expanded: expandedNodes.has(node.id),
          onToggleExpand: () => toggleExpand(node.id),
        },
      })),
    [layoutedNodes, expandedNodes, toggleExpand],
  );

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodesWithCallbacks}
        edges={layoutedEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
        colorMode="dark"
      >
        <Background color="#1e293b" gap={20} size={1} />
        <Controls
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 8,
          }}
        />
        <MiniMap
          nodeColor={() =>
            section === "modeling" ? "#3B82F6" : "#8B5CF6"
          }
          maskColor="rgba(11, 15, 20, 0.8)"
          style={{
            background: "#0d1219",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 8,
          }}
        />
        <Panel position="top-right">
          <div className="px-3 py-1.5 rounded-lg bg-white/5 border border-white/10 text-xs text-gray-500 font-light">
            {entryPoint}
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
