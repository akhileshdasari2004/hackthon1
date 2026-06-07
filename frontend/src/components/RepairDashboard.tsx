"use client";

import { motion } from "framer-motion";
import { CheckCircle, Clock, FileCheck, Gauge, Shield, Zap } from "lucide-react";

import type { Issue } from "@/types";
import { formatDuration } from "@/lib/utils";

interface RepairDashboardProps {
  repairMetrics?: {
    issues_found?: number;
    auto_fixable?: number;
    patch_attempts?: number;
    validated_patches?: number;
    failed_patches?: number;
    repair_rate?: number;
    time_saved_minutes?: number;
    time_saved_hours?: number;
    manual_fixes_avoided?: number;
    files_cleaned?: number;
    validation_success_rate?: number;
  };
  developerReport?: {
    auto_fix_summary?: {
      fixes_applied?: number;
      manual_fixes_avoided?: number;
      files_cleaned?: number;
      validation_success_rate?: number;
      estimated_time_saved_minutes?: number;
      estimated_time_saved_hours?: number;
    };
    repository_health?: {
      health_score?: number;
      issues_found?: number;
      auto_fixable_count?: number;
    };
    top_risk_files?: Array<{ file: string; issue_count: number }>;
    reliability?: { count: number };
    security?: { count: number };
    maintainability?: { count: number };
    code_hygiene?: { count: number };
  };
  issues?: Issue[];
}

export function RepairDashboard({ repairMetrics, developerReport, issues }: RepairDashboardProps) {
  // Get values from either repairMetrics or developerReport
  const metrics = {
    issuesFound: repairMetrics?.issues_found ?? developerReport?.repository_health?.issues_found ?? 0,
    autoFixable: repairMetrics?.auto_fixable ?? developerReport?.repository_health?.auto_fixable_count ?? 0,
    fixesApplied: repairMetrics?.validated_patches ?? developerReport?.auto_fix_summary?.fixes_applied ?? 0,
    repairRate: repairMetrics?.repair_rate ?? developerReport?.auto_fix_summary?.validation_success_rate ?? 0,
    timeSavedMinutes: repairMetrics?.time_saved_minutes ?? developerReport?.auto_fix_summary?.estimated_time_saved_minutes ?? 0,
    timeSavedHours: repairMetrics?.time_saved_hours ?? developerReport?.auto_fix_summary?.estimated_time_saved_hours ?? 0,
    manualFixesAvoided: repairMetrics?.manual_fixes_avoided ?? developerReport?.auto_fix_summary?.manual_fixes_avoided ?? 0,
    filesCleaned: repairMetrics?.files_cleaned ?? developerReport?.auto_fix_summary?.files_cleaned ?? 0,
    validationRate: repairMetrics?.validation_success_rate ?? developerReport?.auto_fix_summary?.validation_success_rate ?? 0,
  };

  // Count issue types
  const issueTypeCounts: Record<string, number> = {};
  const fileRiskCounts: Record<string, number> = {};
  
  issues?.forEach((issue) => {
    const type = issue.pattern ?? issue.type ?? "unknown";
    issueTypeCounts[type] = (issueTypeCounts[type] || 0) + 1;
    
    if (issue.file) {
      fileRiskCounts[issue.file] = (fileRiskCounts[issue.file] || 0) + 1;
    }
  });

  // Top 5 issue types
  const topIssueTypes = Object.entries(issueTypeCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  // Top 5 risk files
  const topRiskFiles = Object.entries(fileRiskCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);

  const stats = [
    {
      label: "Auto Fixable",
      value: metrics.autoFixable,
      icon: Zap,
      color: "text-emerald-600",
      bgColor: "bg-emerald-50 border-emerald-200",
    },
    {
      label: "Fixes Applied",
      value: metrics.fixesApplied,
      icon: CheckCircle,
      color: "text-blue-600",
      bgColor: "bg-blue-50 border-blue-200",
    },
    {
      label: "Validated",
      value: `${Math.round(metrics.validationRate)}%`,
      icon: Shield,
      color: "text-purple-600",
      bgColor: "bg-purple-50 border-purple-200",
    },
    {
      label: "Repair Rate",
      value: `${Math.round(metrics.repairRate)}%`,
      icon: Gauge,
      color: "text-orange-600",
      bgColor: "bg-orange-50 border-orange-200",
    },
    {
      label: "Time Saved",
      value: metrics.timeSavedHours > 0 ? `${metrics.timeSavedHours}h` : `${metrics.timeSavedMinutes}m`,
      icon: Clock,
      color: "text-cyan-600",
      bgColor: "bg-cyan-50 border-cyan-200",
    },
    {
      label: "Files Cleaned",
      value: metrics.filesCleaned,
      icon: FileCheck,
      color: "text-indigo-600",
      bgColor: "bg-indigo-50 border-indigo-200",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        {stats.map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, delay: i * 0.05 }}
            className={`rounded-xl border p-4 ${stat.bgColor}`}
          >
            <div className="flex items-center gap-2">
              <stat.icon className={`h-4 w-4 ${stat.color}`} />
              <p className="text-xs font-medium text-muted-foreground">{stat.label}</p>
            </div>
            <p className={`mt-2 text-2xl font-semibold ${stat.color}`}>
              {typeof stat.value === 'number' ? stat.value : stat.value}
            </p>
          </motion.div>
        ))}
      </div>

      {/* Developer Value Summary */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, delay: 0.3 }}
        className="rounded-xl border border-border bg-gradient-to-r from-emerald-50 to-cyan-50 p-5"
      >
        <h3 className="text-sm font-medium text-foreground">Developer Value</h3>
        <div className="mt-3 grid grid-cols-3 gap-4">
          <div>
            <p className="text-2xl font-semibold text-emerald-600">
              {metrics.manualFixesAvoided}
            </p>
            <p className="text-xs text-muted-foreground">Manual Fixes Avoided</p>
          </div>
          <div>
            <p className="text-2xl font-semibold text-blue-600">
              {metrics.timeSavedHours > 0 
                ? `${metrics.timeSavedHours.toFixed(1)}h` 
                : `${metrics.timeSavedMinutes}m`}
            </p>
            <p className="text-xs text-muted-foreground">Time Saved</p>
          </div>
          <div>
            <p className="text-2xl font-semibold text-indigo-600">
              {metrics.filesCleaned}
            </p>
            <p className="text-xs text-muted-foreground">Files Cleaned</p>
          </div>
        </div>
      </motion.div>

      {/* Two Column Layout: Most Common Issues + Highest Risk Files */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Most Common Issues */}
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.4 }}
          className="rounded-xl border border-border p-5"
        >
          <h3 className="text-sm font-medium text-foreground">Most Common Issues</h3>
          <div className="mt-4 space-y-2">
            {topIssueTypes.length > 0 ? (
              topIssueTypes.map(([type, count]) => (
                <div key={type} className="flex items-center justify-between">
                  <span className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs font-medium text-neutral-700">
                    {type}
                  </span>
                  <span className="text-sm text-muted-foreground">{count}</span>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No issues detected.</p>
            )}
          </div>
        </motion.div>

        {/* Highest Risk Files */}
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, delay: 0.5 }}
          className="rounded-xl border border-border p-5"
        >
          <h3 className="text-sm font-medium text-foreground">Highest Risk Files</h3>
          <div className="mt-4 space-y-2">
            {topRiskFiles.length > 0 ? (
              topRiskFiles.map(([file, count]) => (
                <div key={file} className="flex items-center justify-between">
                  <span className="truncate font-mono text-xs text-foreground" title={file}>
                    {file}
                  </span>
                  <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700">
                    {count}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No risk files identified.</p>
            )}
          </div>
        </motion.div>
      </div>
    </div>
  );
}