"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { HistoryCard } from "@/components/HistoryCard";
import { api } from "@/lib/api";

export default function HistoryPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["history"],
    queryFn: api.getHistory,
  });

  return (
    <div className="mx-auto max-w-4xl px-6 py-12">
      <h1 className="text-3xl font-semibold tracking-tight">History</h1>
      <p className="mt-2 text-muted-foreground">Previous repository analysis runs.</p>

      <div className="mt-10 space-y-4">
        {isLoading && <p className="text-sm text-muted-foreground">Loading history…</p>}
        {error && <p className="text-sm text-red-600">Failed to load history.</p>}
        {data?.length === 0 && (
          <div className="flex flex-col items-center gap-4 rounded-2xl border border-dashed border-border py-16 text-center">
            <svg className="h-12 w-12 text-muted-foreground/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            <div>
              <p className="font-medium text-foreground">No runs yet</p>
              <p className="mt-1 text-sm text-muted-foreground">Start your first repository analysis.</p>
            </div>
            <Link
              href="/analysis"
              className="inline-flex items-center gap-2 rounded-full border border-border bg-background px-5 py-2 text-sm font-medium transition-colors hover:bg-muted"
            >
              Go to Analysis
            </Link>
          </div>
        )}
        {data?.map((entry, i) => (
          <HistoryCard key={entry.job_id} entry={entry} index={i} />
        ))}
      </div>
    </div>
  );
}
