export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

export const JOBS_DIR =
  process.env.AGIRA_JOBS_DIR ?? `${process.cwd()}/../.agira-jobs`;

export const PYTHON_BIN = process.env.PYTHON_BIN ?? "python3";

export const PROJECT_ROOT =
  process.env.AGIRA_PROJECT_ROOT ?? `${process.cwd()}/..`;

export const MEMORY_STORE_PATH =
  process.env.AGIRA_MEMORY_PATH ??
  `${process.env.HOME ?? ""}/.agira/memory_store.json`;

export const SETTINGS_PATH =
  process.env.AGIRA_SETTINGS_PATH ?? `${process.cwd()}/../.agira/settings.json`;

export const DEFAULT_SETTINGS = {
  parallel_scheduling: true,
  self_healing: true,
  memory_layer: true,
  adaptive_planning: true,
  plugin_system: false,
} as const;
