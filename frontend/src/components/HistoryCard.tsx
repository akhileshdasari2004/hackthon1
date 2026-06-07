"use client";

import Link from "next/link";
import { motion } from "framer-motion";

import { formatDate, formatDuration } from "@/lib/utils";
import type { HistoryEntry } from "@/types";

interface HistoryCardProps {
  entry: HistoryEntry;
  index?: number;
}

export function HistoryCard({ entry, index = 0 }: HistoryCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay: index * 0.04 }}
    >
      <Link
        href={`/analysis?job_id=${entry.job_id}`}
        className="block rounded-xl border border-border bg-background p-6 transition-colors duration-200 hover:border-foreground/20 hover:bg-muted"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="font-medium text-foreground">{entry.repo_name}</h3>
            <p className="mt-1 text-sm text-muted-foreground">{formatDate(entry.date)}</p>
          </div>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              entry.success
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300"
                : "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
            }`}
          >
            {entry.success ? "Success" : "Failed"}
          </span>
        </div>
        <div className="mt-4 flex items-center gap-6 text-sm text-muted-foreground">
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
              entry.health_score >= 80
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300"
                : entry.health_score >= 60
                ? "bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300"
                : "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
            }`}
          >
            Health {entry.health_score}
          </span>
          <span>{formatDuration(entry.duration_ms)}</span>
          <span>{entry.issue_count} issues</span>
        </div>
      </Link>
    </motion.div>
  );
}