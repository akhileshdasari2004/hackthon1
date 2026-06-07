import { create } from "zustand";

import type { DagNode, JobResult, RepoInfo } from "@/types";

interface AnalysisState {
  jobId: string | null;
  status: "idle" | "queued" | "running" | "completed" | "failed";
  progress: number;
  nodes: DagNode[];
  repoInfo: RepoInfo | null;
  result: JobResult | null;
  selectedNode: string | null;
  error: string | null;
  setJobId: (id: string | null) => void;
  setStatus: (status: AnalysisState["status"], progress?: number) => void;
  setNodes: (nodes: DagNode[]) => void;
  setRepoInfo: (info: RepoInfo | null) => void;
  setResult: (result: JobResult | null) => void;
  setSelectedNode: (node: string | null) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const useAnalysisStore = create<AnalysisState>((set) => ({
  jobId: null,
  status: "idle",
  progress: 0,
  nodes: [],
  repoInfo: null,
  result: null,
  selectedNode: null,
  error: null,
  setJobId: (jobId) => set({ jobId }),
  setStatus: (status, progress) =>
    set((s) => ({ status, progress: progress ?? s.progress })),
  setNodes: (nodes) => set({ nodes }),
  setRepoInfo: (repoInfo) => set({ repoInfo }),
  setResult: (result) => set({ result }),
  setSelectedNode: (selectedNode) => set({ selectedNode }),
  setError: (error) => set({ error }),
  reset: () =>
    set({
      jobId: null,
      status: "idle",
      progress: 0,
      nodes: [],
      repoInfo: null,
      result: null,
      selectedNode: null,
      error: null,
    }),
}));
