"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Issue, JobResult } from "@/types";

import { HealthScoreCard } from "./HealthScoreCard";
import { PatchViewer } from "./PatchViewer";
import { RepairDashboard } from "./RepairDashboard";

interface ReportTabsProps {
  result: JobResult;
}

export function ReportTabs({ result }: ReportTabsProps) {
  const issueCount = result.issues?.length ?? 0;
  const successRate = result.success ? 100 : 0;

  return (
    <Tabs defaultValue="overview">
      <TabsList>
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="repair">Repair</TabsTrigger>
        <TabsTrigger value="issues">Issues</TabsTrigger>
        <TabsTrigger value="fixes">Fixes</TabsTrigger>
        <TabsTrigger value="metrics">Metrics</TabsTrigger>
      </TabsList>

      <TabsContent value="overview">
        <HealthScoreCard
          healthScore={result.health_score ?? 0}
          issueCount={issueCount}
          executionTimeMs={result.duration_ms ?? result.report?.execution_time_ms ?? 0}
          successRate={successRate}
        />
      </TabsContent>

      <TabsContent value="repair">
        <RepairDashboard
          repairMetrics={result.repair_metrics}
          developerReport={result.developer_report}
          issues={result.issues ?? []}
        />
      </TabsContent>

      <TabsContent value="issues">
        <IssuesList issues={result.issues ?? []} />
      </TabsContent>

      <TabsContent value="fixes">
        <PatchViewer patches={result.patches ?? []} />
      </TabsContent>

      <TabsContent value="metrics">
        <MetricsPanel result={result} />
      </TabsContent>
    </Tabs>
  );
}

function IssuesList({ issues }: { issues: Issue[] }) {
  if (!issues.length) {
    return <p className="text-sm text-muted-foreground">No issues detected.</p>;
  }
  return (
    <div className="space-y-3">
      {issues.map((issue, i) => (
        <div key={i} className="rounded-xl border border-border p-4">
          <p className="font-medium text-foreground">
            {issue.type ?? issue.category ?? issue.pattern ?? "Issue"}
          </p>
          <p className="mt-1 text-sm text-neutral-600">
            {issue.description ?? issue.file ?? "—"}
          </p>
          {issue.file && (
            <p className="mt-2 font-mono text-xs text-muted-foreground">
              {issue.file}
              {issue.line != null ? `:${issue.line}` : ""}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

function MetricsPanel({ result }: { result: JobResult }) {
  const report = result.report;
  const rows = [
    ["Nodes Executed", report?.nodes_executed],
    ["Nodes Completed", report?.nodes_completed],
    ["Nodes Failed", report?.nodes_failed],
    ["Tool Calls", report?.tool_calls],
    ["Parallel Gain", report?.parallel_gain_pct != null ? `${report.parallel_gain_pct.toFixed(1)}%` : "—"],
    ["Self Healing", report?.self_healing_triggered ? "Yes" : "No"],
    ["Memory Used", report?.memory_used ? "Yes" : "No"],
  ];

  return (
    <div className="rounded-xl border border-border divide-y divide-neutral-200">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between px-4 py-3 text-sm">
          <span className="text-muted-foreground">{label}</span>
          <span className="font-medium text-foreground">{value ?? "—"}</span>
        </div>
      ))}
    </div>
  );
}
