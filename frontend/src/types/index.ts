export type NodeState = "pending" | "running" | "success" | "failed" | "skipped";

export interface DagNode {
  name: string;
  status: NodeState;
  action_type?: "tool" | "subagent";
  target?: string;
  batch?: number;
  duration_ms?: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
  retry_count?: number;
}

export interface RepoInfo {
  name: string;
  path: string;
  language: string;
  file_count: number;
  lines: number;
  url?: string;
}

export interface Issue {
  file?: string;
  pattern?: string;
  type?: string;
  description?: string;
  line?: number;
  category?: string;
}

export interface Patch {
  file?: string;
  rel_path?: string;
  path?: string;
  pattern?: string;
  diff?: string;
  validated?: boolean;
}

export interface AnalyzeRequest {
  repo_url?: string;
  repo_path?: string;
  options?: AgiraSettings;
}

export interface AgiraSettings {
  parallel_scheduling: boolean;
  self_healing: boolean;
  memory_layer: boolean;
  adaptive_planning: boolean;
  plugin_system: boolean;
}

export interface AnalyzeResponse {
  job_id: string;
  status: string;
}

export interface StatusResponse {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress: number;
  current_node?: string;
  nodes: DagNode[];
  logs: LogEntry[];
}

export interface LogEntry {
  id?: string;
  timestamp: string | number;
  level?: string;
  source?: string;
  message: string;
}

export interface TimelineEvent {
  node: string;
  batch: number;
  event: string;
  timestamp: string;
  duration_ms?: number;
}

export interface ExecutionTimeline {
  node_timeline: TimelineEvent[];
  batch_timings: Array<{
    batch_id: number;
    nodes: string[];
    duration_ms: number;
    is_parallel: boolean;
  }>;
  parallel_gain_pct: number;
}

export interface FinalReport {
  dag_status: string;
  nodes_executed: number;
  nodes_completed: number;
  nodes_failed: number;
  execution_time_ms: number;
  parallel_gain_pct: number;
  tool_calls: number;
  self_healing_triggered: boolean;
  memory_used: boolean;
  node_details: DagNode[];
}

export interface RepairMetrics {
  issues_found: number;
  auto_fixable: number;
  patch_attempts: number;
  successful_patches: number;
  failed_patches: number;
  validated_patches: number;
  rollbacks: number;
  repair_rate: number;
  validation_rate: number;
  time_saved_minutes: number;
  time_saved_hours: number;
  manual_fixes_avoided: number;
  files_cleaned: number;
  validation_success_rate: number;
}

export interface DeveloperReport {
  repository_health: {
    health_score: number;
    health_grade: string;
    issues_found: number;
    auto_fixable_count: number;
    auto_fixable_percent: number;
  };
  reliability: { count: number; issues: Issue[] };
  security: { count: number; issues: Issue[] };
  maintainability: { count: number; issues: Issue[] };
  code_hygiene: { count: number; issues: Issue[] };
  auto_fix_summary: {
    fixes_applied: number;
    manual_fixes_avoided: number;
    files_cleaned: number;
    failed: number;
    rolled_back: number;
    validation_success_rate: number;
    success_rate: number;
    estimated_time_saved_minutes: number;
    estimated_time_saved_hours: number;
  };
  remaining_issues: { count: number; issues: Issue[] };
  technical_debt: { count: number; issues: Issue[] };
  top_risk_files: Array<{ file: string; issue_count: number }>;
  developer_value: {
    time_saved_minutes: number;
    time_saved_hours: number;
    manual_fixes_avoided: number;
    files_cleaned: number;
    validation_success_rate: number;
    focus_remaining_minutes: number;
    focus_remaining_hours: number;
  };
}

export interface JobResult {
  job_id: string;
  status: string;
  success: boolean;
  duration_ms: number;
  report: FinalReport;
  timeline: ExecutionTimeline;
  issues: Issue[];
  patches: Patch[];
  validation: Record<string, unknown>;
  health_score: number;
  markdown_report: string;
  repo_info: RepoInfo;
  nodes: DagNode[];
  repair_metrics?: RepairMetrics;
  developer_report?: DeveloperReport;
}

export interface HistoryEntry {
  job_id: string;
  repo_name: string;
  repo_url?: string;
  date: string;
  duration_ms: number;
  health_score: number;
  success: boolean;
  issue_count: number;
}

export interface MemoryData {
  failures: Record<string, Record<string, unknown>>;
  successes: Record<string, unknown>;
  repo_profiles: Record<string, unknown>;
  tool_metrics: Record<string, unknown>;
  learning_log: Array<{ event: string; data: Record<string, unknown>; timestamp?: string }>;
}
