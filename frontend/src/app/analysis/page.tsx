"use client";

import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { RepositoryUploader } from "@/components/RepositoryUploader";
import { api } from "@/lib/api";
import { useAnalysisPolling } from "@/hooks/useAnalysisPolling";
import { useAnalysisStore } from "@/lib/store";

const DAGGraph = dynamic(
  () => import("@/components/DAGGraph").then((m) => m.DAGGraph),
  { ssr: false },
);
const ExecutionTimeline = dynamic(
  () => import("@/components/ExecutionTimeline").then((m) => m.ExecutionTimeline),
  { ssr: false },
);
const ReportTabs = dynamic(
  () => import("@/components/ReportTabs").then((m) => m.ReportTabs),
  { ssr: false },
);
const PatchViewer = dynamic(
  () => import("@/components/PatchViewer").then((m) => m.PatchViewer),
  { ssr: false },
);
const MemoryPanel = dynamic(
  () => import("@/components/MemoryPanel").then((m) => m.MemoryPanel),
  { ssr: false },
);

function AnalysisContent() {
  const searchParams = useSearchParams();
  const [loading, setLoading] = useState(false);
  const {
    jobId,
    status,
    progress,
    nodes,
    repoInfo,
    result,
    selectedNode,
    error,
    setJobId,
    setStatus,
    setError,
    setSelectedNode,
    reset,
  } = useAnalysisStore();

  useAnalysisPolling(jobId);

  const startAnalysis = useCallback(
    async (input: { repo_url?: string; repo_path?: string }) => {
      setLoading(true);
      setError(null);
      reset();
      try {
        const res = await api.analyze({ ...input });
        setJobId(res.job_id);
        setStatus("queued", 0);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start analysis");
      } finally {
        setLoading(false);
      }
    },
    [reset, setJobId, setStatus, setError],
  );

  // Initialize from URL params on mount — runs once
  useEffect(() => {
    const existingJob = searchParams.get("job_id");
    const isDemo = searchParams.get("demo");
    if (existingJob) {
      setJobId(existingJob);
      setStatus("running");
    } else if (isDemo) {
      setJobId(null);
      setStatus("queued", 0);
      api.analyze({ repo_path: "examples/buggy_calculator" }).then(
        (res) => setJobId(res.job_id),
        (err) => setError(err instanceof Error ? err.message : "Failed to start analysis"),
      );
    }
  }, [searchParams, setJobId, setStatus, setError]);

  const selectedNodeData = nodes.find((n) => n.name === selectedNode);
  const isRunning = status === "running" || status === "queued";

  return (
    <div className="mx-auto max-w-[1600px] px-6 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">Analysis</h1>
        <p className="mt-2 text-muted-foreground">
          Live DAG execution with audit, repair, and validation.
        </p>
      </div>

      {error && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-12">
        <aside className="lg:col-span-3">
          <div className="sticky top-24 rounded-2xl border border-border bg-background p-6">
            <RepositoryUploader
              repoInfo={result?.repo_info ?? repoInfo}
              loading={loading || isRunning}
              onAnalyze={startAnalysis}
            />
          </div>
        </aside>

        <section className="lg:col-span-5">
          <div className="rounded-2xl border border-border bg-background p-6">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-sm font-medium">DAG Execution</h2>
              {isRunning && (
                <span className="text-xs text-muted-foreground">{progress}%</span>
              )}
            </div>
            <DAGGraph
              nodes={result?.nodes ?? nodes}
              selectedNode={selectedNode ?? undefined}
              onSelectNode={setSelectedNode}
            />
          </div>
        </section>

        <aside className="space-y-6 lg:col-span-4">
          <div className="rounded-2xl border border-border bg-background p-6">
            <h2 className="text-sm font-medium">Execution Details</h2>
            {selectedNodeData ? (
              <div className="mt-4 space-y-2 text-sm">
                <p>
                  <span className="text-muted-foreground">Node</span>{" "}
                  <span className="font-medium">{selectedNodeData.name}</span>
                </p>
                <p>
                  <span className="text-muted-foreground">Status</span>{" "}
                  <span className="font-medium capitalize">{selectedNodeData.status}</span>
                </p>
                {selectedNodeData.target && (
                  <p>
                    <span className="text-muted-foreground">Target</span>{" "}
                    <span className="font-medium">{selectedNodeData.target}</span>
                  </p>
                )}
              </div>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">Select a node to view details.</p>
            )}
            <div className="mt-6 border-t border-border pt-6">
              <ExecutionTimeline timeline={result?.timeline} />
            </div>
          </div>

          {result && (
            <div className="rounded-2xl border border-border bg-background p-6">
              <h2 className="mb-4 text-sm font-medium">Patches</h2>
              <PatchViewer patches={result.patches ?? []} />
            </div>
          )}

          <div className="rounded-2xl border border-border bg-background p-6">
            <h2 className="mb-4 text-sm font-medium">Memory</h2>
            <MemoryPanel />
          </div>
        </aside>
      </div>

      {result && (
        <div className="mt-8 rounded-2xl border border-border bg-background p-6">
          <h2 className="mb-6 text-lg font-medium">Report</h2>
          <ReportTabs result={result} />
        </div>
      )}
    </div>
  );
}

export default function AnalysisPage() {
  return (
    <Suspense fallback={<div className="p-8 text-muted-foreground">Loading…</div>}>
      <AnalysisContent />
    </Suspense>
  );
}
