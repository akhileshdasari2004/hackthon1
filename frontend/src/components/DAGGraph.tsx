"use client";

import { motion } from "framer-motion";
import { memo, useMemo } from "react";

import { DAG_LAYOUT, mergeNodesWithLayout } from "@/lib/dag";
import { cn } from "@/lib/utils";
import type { DagNode } from "@/types";

import { NodeCard } from "./NodeCard";

interface DAGGraphProps {
  nodes: DagNode[];
  selectedNode?: string;
  onSelectNode?: (name: string) => void;
}

function DAGGraphComponent({ nodes, selectedNode, onSelectNode }: DAGGraphProps) {
  const merged = useMemo(() => mergeNodesWithLayout(nodes), [nodes]);

  const byBatch = useMemo(() => {
    const batches = new Map<number, typeof merged>();
    for (const node of merged) {
      const layout = DAG_LAYOUT.find((l) => l.id === node.name);
      const batch = layout?.batch ?? node.batch ?? 0;
      if (!batches.has(batch)) batches.set(batch, []);
      batches.get(batch)!.push(node);
    }
    return [...batches.entries()].sort(([a], [b]) => a - b);
  }, [merged]);

  return (
    <div className="space-y-8">
      {byBatch.map(([batch, batchNodes], idx) => (
        <motion.div
          key={batch}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: idx * 0.05 }}
          className="relative"
        >
          {batchNodes.length > 1 && (
            <div className="mb-3 flex items-center gap-2">
              <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Parallel
              </span>
              <div className="h-px flex-1 bg-border" />
            </div>
          )}
          <div
            className={cn(
              "grid gap-3",
              batchNodes.length > 1 ? "grid-cols-2" : "grid-cols-1",
            )}
          >
            {batchNodes.map((node) => {
              const layout = DAG_LAYOUT.find((l) => l.id === node.name);
              return (
                <NodeCard
                  key={node.name}
                  node={node}
                  label={layout?.label}
                  selected={selectedNode === node.name}
                  onClick={() => onSelectNode?.(node.name)}
                />
              );
            })}
          </div>
          {idx < byBatch.length - 1 && (
            <div className="mx-auto mt-6 flex flex-col items-center">
              <div className="h-6 w-px bg-border" />
              <div className="h-2 w-2 rotate-45 border-b border-r border-border" />
            </div>
          )}
        </motion.div>
      ))}
    </div>
  );
}

export const DAGGraph = memo(DAGGraphComponent);
