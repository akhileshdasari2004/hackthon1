"use client";

import { motion } from "framer-motion";
import { memo } from "react";

import { statusColor } from "@/lib/dag";
import { cn } from "@/lib/utils";
import type { DagNode } from "@/types";

interface NodeCardProps {
  node: DagNode;
  label?: string;
  selected?: boolean;
  onClick?: () => void;
}

function NodeCardComponent({ node, label, selected, onClick }: NodeCardProps) {
  const display = label ?? node.name.replace(/_/g, " ");

  return (
    <motion.button
      type="button"
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      onClick={onClick}
      className={cn(
        "w-full rounded-xl border px-4 py-3 text-left transition-colors duration-200",
        statusColor(node.status),
        selected && "ring-2 ring-foreground ring-offset-2",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium capitalize text-foreground">{display}</span>
        <StatusDot status={node.status} />
      </div>
      {node.duration_ms != null && (
        <p className="mt-1 text-xs text-muted-foreground">{node.duration_ms}ms</p>
      )}
      {node.error && <p className="mt-1 text-xs text-red-600">{node.error}</p>}
    </motion.button>
  );
}

function StatusDot({ status }: { status: DagNode["status"] }) {
  const colors: Record<DagNode["status"], string> = {
    pending: "bg-muted-foreground/30",
    running: "bg-foreground animate-pulse",
    success: "bg-emerald-600",
    failed: "bg-red-600",
    skipped: "bg-muted-foreground/40",
  };
  return <span className={cn("h-2 w-2 shrink-0 rounded-full", colors[status])} />;
}

export const NodeCard = memo(NodeCardComponent);