"use client";

import { useCallback, useEffect, useRef } from "react";

import { api } from "@/lib/api";
import { useAnalysisStore } from "@/lib/store";

export function useAnalysisPolling(jobId: string | null) {
  const {
    setStatus,
    setNodes,
    setResult,
    setError,
    setRepoInfo,
  } = useAnalysisStore();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = useCallback(async () => {
    if (!jobId) return;
    try {
      const status = await api.getStatus(jobId);
      setStatus(status.status as "queued" | "running" | "completed" | "failed", status.progress);
      if (status.nodes?.length) setNodes(status.nodes);

      if (status.status === "completed" || status.status === "failed") {
        const result = await api.getReport(jobId);
        setResult(result);
        if (result.repo_info) setRepoInfo(result.repo_info);
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Polling failed");
    }
  }, [jobId, setStatus, setNodes, setResult, setError, setRepoInfo]);

  useEffect(() => {
    if (!jobId) return;
    poll();
    intervalRef.current = setInterval(poll, 1500);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [jobId, poll]);
}
