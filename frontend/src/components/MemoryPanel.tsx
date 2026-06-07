"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export function MemoryPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["memory"],
    queryFn: api.getMemory,
  });

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading memory…</p>;
  if (error) return <p className="text-sm text-red-600">Failed to load memory.</p>;
  if (!data) return null;

  const failures = Object.entries(data.failures ?? {});
  const successes = Object.entries(data.successes ?? {});
  const optimizations = (data.learning_log ?? []).slice(-5).reverse();

  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-sm font-medium text-foreground">Known Failures</h3>
        <div className="mt-3 space-y-2">
          {failures.length === 0 ? (
            <p className="text-sm text-muted-foreground">None recorded.</p>
          ) : (
            failures.slice(0, 5).map(([key, val]) => {
            const display =
              typeof val === "object" && val !== null
                ? `${val.count ?? ""} · ${val.error_type ?? ""}`.trim() || JSON.stringify(val).slice(0, 80)
                : String(val);
            return (
              <div key={key} className="rounded-lg border border-border px-3 py-2 text-sm">
                <span className="font-medium text-foreground">{key}</span>
                <span className="ml-2 text-muted-foreground">{display}</span>
              </div>
            );
          })
          )}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium text-foreground">Success Patterns</h3>
        <div className="mt-3 space-y-2">
          {successes.length === 0 ? (
            <p className="text-sm text-muted-foreground">None recorded.</p>
          ) : (
            successes.slice(0, 5).map(([key]) => (
              <div key={key} className="rounded-lg border border-border px-3 py-2 text-sm">
                {key}
              </div>
            ))
          )}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-medium text-foreground">Learned Optimizations</h3>
        <div className="mt-3 space-y-2">
          {optimizations.length === 0 ? (
            <p className="text-sm text-muted-foreground">None recorded.</p>
          ) : (
            optimizations.map((entry, i) => (
              <div key={i} className="rounded-lg border border-border px-3 py-2 text-sm text-muted-foreground">
                {entry.event}
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}