"use client";

import type { Patch } from "@/types";

interface PatchViewerProps {
  patches: Patch[];
}

export function PatchViewer({ patches }: PatchViewerProps) {
  if (!patches.length) {
    return <p className="text-sm text-muted-foreground">No patches generated.</p>;
  }

  return (
    <div className="space-y-4">
      {patches.map((patch, i) => {
        const file = patch.file ?? patch.rel_path ?? patch.path ?? `patch-${i}`;
        const diff = patch.diff ?? formatPatchFallback(patch);
        return (
          <div key={`${file}-${i}`} className="overflow-hidden rounded-xl border border-border">
            <div className="border-b border-border bg-muted px-4 py-2 text-sm font-medium">
              {file}
            </div>
            <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed">
              {diff.split("\n").map((line, li) => (
                <div
                  key={li}
                  className={
                    line.startsWith("+")
                      ? "diff-added px-2"
                      : line.startsWith("-")
                        ? "diff-removed px-2"
                        : "px-2 text-muted-foreground"
                  }
                >
                  {line || " "}
                </div>
              ))}
            </pre>
          </div>
        );
      })}
    </div>
  );
}

function formatPatchFallback(patch: Patch): string {
  const lines: string[] = [];
  if (patch.pattern) lines.push(`# Pattern: ${patch.pattern}`);
  if (patch.validated != null) lines.push(`# Validated: ${patch.validated}`);
  return lines.join("\n") || "# No diff available";
}