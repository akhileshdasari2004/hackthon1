"use client";

import { motion } from "framer-motion";

import { formatDuration } from "@/lib/utils";

interface HealthScoreCardProps {
  healthScore: number;
  issueCount: number;
  executionTimeMs: number;
  successRate: number;
}

export function HealthScoreCard({
  healthScore,
  issueCount,
  executionTimeMs,
  successRate,
}: HealthScoreCardProps) {
  const metrics = [
    { label: "Health Score", value: `${healthScore}` },
    { label: "Issues", value: `${issueCount}` },
    { label: "Execution Time", value: formatDuration(executionTimeMs) },
    { label: "Success Rate", value: `${Math.round(successRate)}%` },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {metrics.map((m, i) => (
        <motion.div
          key={m.label}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: i * 0.05 }}
          className="rounded-xl border border-border bg-background p-5"
        >
          <p className="text-sm text-muted-foreground">{m.label}</p>
          <p className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
            {m.value}
          </p>
        </motion.div>
      ))}
    </div>
  );
}
