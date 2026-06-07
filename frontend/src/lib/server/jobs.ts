import { spawn } from "child_process";
import { randomUUID } from "crypto";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "fs";
import path from "path";

import { DEFAULT_SETTINGS, JOBS_DIR, PROJECT_ROOT, PYTHON_BIN, SETTINGS_PATH } from "@/lib/config";
import type { AgiraSettings, HistoryEntry } from "@/types";

const HISTORY_PATH = path.join(path.dirname(JOBS_DIR), ".agira-history.json");

export function ensureJobsDir(): string {
  if (!existsSync(JOBS_DIR)) mkdirSync(JOBS_DIR, { recursive: true });
  return JOBS_DIR;
}

export function createJob(repoPath: string, settings: Partial<AgiraSettings> = {}): string {
  const jobId = randomUUID();
  const jobDir = path.join(ensureJobsDir(), jobId);
  mkdirSync(jobDir, { recursive: true });

  const meta = {
    job_id: jobId,
    repo_path: repoPath,
    created_at: new Date().toISOString(),
    settings: { ...loadSettings(), ...settings },
  };
  writeFileSync(path.join(jobDir, "meta.json"), JSON.stringify(meta, null, 2));

  const runner = path.join(PROJECT_ROOT, "scripts", "job_runner.py");
  const proc = spawn(PYTHON_BIN, [runner, jobDir, repoPath, JSON.stringify(meta.settings)], {
    cwd: PROJECT_ROOT,
    detached: true,
    stdio: "ignore",
  });
  proc.unref();

  return jobId;
}

export function readJobStatus(jobId: string) {
  const jobDir = path.join(ensureJobsDir(), jobId);
  const statusPath = path.join(jobDir, "status.json");
  if (!existsSync(statusPath)) {
    return { job_id: jobId, status: "queued" as const, progress: 0, nodes: [], logs: [] };
  }
  const data = JSON.parse(readFileSync(statusPath, "utf-8"));
  return { job_id: jobId, ...data };
}

export function readJobResult(jobId: string) {
  const jobDir = path.join(ensureJobsDir(), jobId);
  const resultPath = path.join(jobDir, "result.json");
  if (!existsSync(resultPath)) return null;
  const data = JSON.parse(readFileSync(resultPath, "utf-8"));
  return { job_id: jobId, ...data };
}

export function readJobMeta(jobId: string) {
  const metaPath = path.join(ensureJobsDir(), jobId, "meta.json");
  if (!existsSync(metaPath)) return null;
  return JSON.parse(readFileSync(metaPath, "utf-8"));
}

export function loadSettings(): AgiraSettings & { plugin_system: boolean } {
  try {
    if (existsSync(SETTINGS_PATH)) {
      return { ...DEFAULT_SETTINGS, ...JSON.parse(readFileSync(SETTINGS_PATH, "utf-8")) };
    }
  } catch {
    /* ignore */
  }
  return { ...DEFAULT_SETTINGS };
}

export function saveSettings(settings: Partial<AgiraSettings & { plugin_system: boolean }>) {
  const dir = path.dirname(SETTINGS_PATH);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  const merged = { ...loadSettings(), ...settings };
  writeFileSync(SETTINGS_PATH, JSON.stringify(merged, null, 2));
  return merged;
}

export function loadHistory(): HistoryEntry[] {
  try {
    if (existsSync(HISTORY_PATH)) {
      return JSON.parse(readFileSync(HISTORY_PATH, "utf-8"));
    }
  } catch {
    /* ignore */
  }
  return [];
}

export function appendHistory(entry: HistoryEntry) {
  const history = loadHistory();
  if (history.some((h) => h.job_id === entry.job_id)) return;
  history.unshift(entry);
  const dir = path.dirname(HISTORY_PATH);
  if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
  writeFileSync(HISTORY_PATH, JSON.stringify(history.slice(0, 100), null, 2));
}

export function syncHistoryFromJobs() {
  const jobsDir = ensureJobsDir();
  const existing = new Set(loadHistory().map((h) => h.job_id));
  const entries: HistoryEntry[] = [];

  for (const jobId of readdirSync(jobsDir)) {
    if (existing.has(jobId)) continue;
    const result = readJobResult(jobId);
    const meta = readJobMeta(jobId);
    if (!result || result.status !== "completed" && result.status !== "failed") continue;
    entries.push({
      job_id: jobId,
      repo_name: result.repo_info?.name ?? meta?.repo_path?.split("/").pop() ?? "Unknown",
      repo_url: meta?.repo_url,
      date: meta?.created_at ?? new Date().toISOString(),
      duration_ms: result.duration_ms ?? 0,
      health_score: result.health_score ?? 0,
      success: result.success ?? false,
      issue_count: result.issues?.length ?? 0,
    });
  }

  if (entries.length) {
    const history = [...entries, ...loadHistory()];
    writeFileSync(HISTORY_PATH, JSON.stringify(history.slice(0, 100), null, 2));
  }
}

// Allowed workspace roots for local repo paths
const WORKSPACE_ROOTS = [
  path.join(PROJECT_ROOT, "examples"),
  path.join(PROJECT_ROOT, "projects"),
  PROJECT_ROOT,
];

// Git URL pattern — supports GitHub, GitLab, Bitbucket, self-hosted git
const _GIT_URL_RE =
  /^https?:\/\/(?:[\w.-]+@)?(?:github|gitlab|bitbucket\.org|[\w.-]+\.[\w]+)[\/][^\s]+$/i;

function _isGitUrl(value: string): boolean {
  return Boolean(_GIT_URL_RE.test(value.trim()));
}

function _isWithinWorkspace(p: string): boolean {
  const resolved = path.resolve(p);
  return WORKSPACE_ROOTS.some((root) => resolved.startsWith(path.resolve(root) + path.sep));
}

export function resolveRepoPath(input: { repo_url?: string; repo_path?: string }): string {
  if (input.repo_path) {
    const abs = path.isAbsolute(input.repo_path)
      ? input.repo_path
      : path.join(PROJECT_ROOT, input.repo_path);
    // Path traversal prevention: reject paths that escape the workspace
    if (abs.includes("..")) {
      throw new Error("Path traversal not allowed");
    }
    if (!_isWithinWorkspace(abs)) {
      throw new Error("Local path must be within the project examples or projects directory");
    }
    if (existsSync(abs)) return abs;
    throw new Error(`Local path not found: ${input.repo_path}`);
  }
  if (input.repo_url) {
    const url = input.repo_url.trim();
    if (!_isGitUrl(url)) {
      throw new Error(
        "Invalid git URL. Must be a GitHub, GitLab, or Bitbucket HTTPS URL (e.g. https://github.com/user/repo)",
      );
    }
    // Return the URL prefixed with "git:" to signal job_runner to clone
    return `git:${url}`;
  }
  // Default demo fallback for local-only deployments
  const demo = path.join(PROJECT_ROOT, "examples", "buggy_calculator");
  if (existsSync(demo)) return demo;
  throw new Error("Provide repo_url (https://github.com/...) or repo_path (examples/...)");
}
