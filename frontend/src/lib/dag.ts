import type { DagNode, NodeState } from "@/types";

export const DAG_LAYOUT: Array<{
  id: string;
  label: string;
  batch: number;
  deps: string[];
}> = [
  { id: "repo_metadata", label: "Repo Metadata", batch: 1, deps: [] },
  { id: "file_list", label: "File List", batch: 1, deps: ["repo_metadata"] },
  { id: "dependency_graph", label: "Dependency Graph", batch: 1, deps: ["file_list"] },
  { id: "bug_detection", label: "Bug Detection", batch: 2, deps: ["dependency_graph"] },
  { id: "repo_analysis", label: "Repo Analysis", batch: 2, deps: ["dependency_graph"] },
  { id: "merge_findings", label: "Merge Findings", batch: 3, deps: ["bug_detection", "repo_analysis"] },
  { id: "patch_generation", label: "Patch Generation", batch: 4, deps: ["merge_findings"] },
  { id: "validation", label: "Validation", batch: 5, deps: ["patch_generation"] },
  { id: "report_generation", label: "Report Generation", batch: 6, deps: ["validation"] },
];

export function mergeNodesWithLayout(nodes: DagNode[]): DagNode[] {
  const byName = new Map(nodes.map((n) => [n.name, n]));
  return DAG_LAYOUT.map((layout) => {
    const live = byName.get(layout.id);
    if (live) return { ...live, batch: layout.batch };
    const alias = layout.id === "validation"
      ? byName.get("test_validation") ?? byName.get("initial_validation")
      : layout.id === "report_generation"
        ? byName.get("json_report") ?? byName.get("markdown_report") ?? byName.get("health_score")
        : undefined;
    if (alias) return { ...alias, name: layout.id, batch: layout.batch };
    return {
      name: layout.id,
      status: "pending" as NodeState,
      batch: layout.batch,
    };
  });
}

export function statusColor(status: NodeState): string {
  switch (status) {
    case "running":
      return "border-foreground bg-muted";
    case "success":
      return "border-emerald-600 bg-emerald-50";
    case "failed":
      return "border-red-600 bg-red-50";
    case "skipped":
      return "border-border bg-muted";
    default:
      return "border-border bg-background";
  }
}
