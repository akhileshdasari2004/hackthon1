"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { RepoInfo } from "@/types";

interface RepositoryUploaderProps {
  repoInfo?: RepoInfo | null;
  loading?: boolean;
  onAnalyze: (input: { repo_url?: string; repo_path?: string }) => void;
}

export function RepositoryUploader({ repoInfo, loading, onAnalyze }: RepositoryUploaderProps) {
  const [mode, setMode] = useState<"url" | "path">("url");
  const [value, setValue] = useState("");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-medium text-foreground">Repository</h2>
        <p className="mt-1 text-sm text-muted-foreground">Connect a GitHub URL or local path.</p>
      </div>

      <div className="flex gap-2">
        {(["url", "path"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            aria-pressed={mode === m}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors duration-200 ${
              mode === m
                ? "bg-foreground text-background"
                : "bg-muted text-muted-foreground hover:bg-muted/80"
            }`}
          >
            {m === "url" ? "GitHub URL" : "Local Path"}
          </button>
        ))}
      </div>

      <Input
        placeholder={mode === "url" ? "https://github.com/org/repo" : "examples/buggy_calculator"}
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />

      <Button
        className="w-full"
        disabled={!value.trim() || loading}
        onClick={() =>
          onAnalyze(mode === "url" ? { repo_url: value } : { repo_path: value })
        }
      >
        {loading ? "Analyzing…" : "Analyze Repository"}
      </Button>

      {repoInfo && (
        <div className="space-y-3 rounded-xl border border-border bg-muted p-4">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Name</span>
            <span className="font-medium text-foreground">{repoInfo.name}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Language</span>
            <span className="font-medium text-foreground">{repoInfo.language}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Files</span>
            <span className="font-medium text-foreground">{repoInfo.file_count}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Lines</span>
            <span className="font-medium text-foreground">{repoInfo.lines.toLocaleString()}</span>
          </div>
        </div>
      )}
    </div>
  );
}