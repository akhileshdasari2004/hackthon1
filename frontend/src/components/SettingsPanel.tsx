"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Switch } from "@/components/ui/switch";
import { api } from "@/lib/api";
import type { AgiraSettings } from "@/types";

type Settings = AgiraSettings & { plugin_system: boolean };

const TOGGLES: Array<{ key: keyof Settings; label: string; description: string }> = [
  {
    key: "parallel_scheduling",
    label: "Parallel Scheduling",
    description: "Run independent DAG nodes concurrently.",
  },
  {
    key: "self_healing",
    label: "Self Healing",
    description: "Automatically retry and repair failed nodes.",
  },
  {
    key: "memory_layer",
    label: "Memory Layer",
    description: "Persist learnings across repository runs.",
  },
  {
    key: "adaptive_planning",
    label: "Adaptive Planning",
    description: "Memory-aware goal ordering that skips known-failure patterns.",
  },
  {
    key: "plugin_system",
    label: "Plugin System",
    description: "Enable extensible tool plugins.",
  },
];

export function SettingsPanel() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["settings"], queryFn: api.getSettings });
  const [localError, setLocalError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: api.updateSettings,
    onSuccess: (updated) => {
      queryClient.setQueryData(["settings"], updated);
      setLocalError(null);
    },
    onError: (err: Error) => {
      setLocalError(err.message ?? "Failed to save settings.");
    },
  });

  if (isLoading || !data) {
    return <p className="text-sm text-muted-foreground">Loading settings…</p>;
  }

  return (
    <div className="space-y-4">
      {localError && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {localError}
        </div>
      )}
      {TOGGLES.map((toggle) => (
        <div
          key={toggle.key}
          className="flex items-center justify-between rounded-xl border border-border p-5"
        >
          <div>
            <p className="font-medium text-foreground">{toggle.label}</p>
            <p className="mt-1 text-sm text-muted-foreground">{toggle.description}</p>
          </div>
          <Switch
            checked={data[toggle.key]}
            disabled={mutation.isPending}
            onCheckedChange={(checked) =>
              mutation.mutate({ [toggle.key]: checked })
            }
          />
        </div>
      ))}
    </div>
  );
}
