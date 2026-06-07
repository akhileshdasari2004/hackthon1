"use client";

import { motion } from "framer-motion";

import { formatDuration } from "@/lib/utils";
import type { ExecutionTimeline as TimelineData } from "@/types";

interface ExecutionTimelineProps {
  timeline?: TimelineData;
}

export function ExecutionTimeline({ timeline }: ExecutionTimelineProps) {
  if (!timeline?.node_timeline?.length && !timeline?.batch_timings?.length) {
    return (
      <p className="text-sm text-muted-foreground">Timeline will appear during execution.</p>
    );
  }

  return (
    <div className="space-y-6">
      {timeline.batch_timings?.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Batches
          </h3>
          {timeline.batch_timings
            .filter((b): b is { batch_id: number; nodes: string[]; duration_ms: number; is_parallel: boolean } =>
              "batch_id" in b && Array.isArray(b.nodes)
            )
            .map((batch) => (
              <motion.div
                key={batch.batch_id}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2 }}
                className="rounded-lg border border-border p-3"
              >
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium">
                    Batch {batch.batch_id}
                    {batch.is_parallel && (
                      <span className="ml-2 text-xs text-muted-foreground">parallel</span>
                    )}
                  </span>
                  <span className="text-muted-foreground">{formatDuration(batch.duration_ms)}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{batch.nodes.join(", ")}</p>
              </motion.div>
            ))}
        </div>
      )}

      {timeline.node_timeline?.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Events
          </h3>
          <div className="max-h-64 space-y-1 overflow-y-auto">
            {timeline.node_timeline.map((event, i) => (
              <div
                key={`${event.node}-${event.timestamp}-${i}`}
                className="flex items-center justify-between rounded-md px-2 py-1.5 text-xs hover:bg-muted"
              >
                <span className="font-medium text-foreground">{event.node}</span>
                <span className="text-muted-foreground">{event.event}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {timeline.parallel_gain_pct > 0 && (
        <p className="text-xs text-muted-foreground">
          Parallel gain: {timeline.parallel_gain_pct.toFixed(1)}%
        </p>
      )}
    </div>
  );
}