import type {
  AgiraSettings,
  AnalyzeRequest,
  AnalyzeResponse,
  HistoryEntry,
  JobResult,
  MemoryData,
  StatusResponse,
} from "@/types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error ?? `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  analyze: (body: AnalyzeRequest) =>
    request<AnalyzeResponse>("/api/analyze", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  getStatus: (jobId: string) =>
    request<StatusResponse>(`/api/analyze?job_id=${encodeURIComponent(jobId)}`),

  getReport: (jobId: string) =>
    request<JobResult>(`/api/report?job_id=${encodeURIComponent(jobId)}`),

  getHistory: () => request<HistoryEntry[]>("/api/history"),

  getMemory: () => request<MemoryData>("/api/memory"),

  getSettings: () => request<AgiraSettings & { plugin_system: boolean }>("/api/settings"),

  updateSettings: (settings: Partial<AgiraSettings & { plugin_system: boolean }>) =>
    request<AgiraSettings & { plugin_system: boolean }>("/api/settings", {
      method: "PUT",
      body: JSON.stringify(settings),
    }),
};
