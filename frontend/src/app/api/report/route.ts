import { NextRequest, NextResponse } from "next/server";

import { appendHistory, readJobMeta, readJobResult } from "@/lib/server/jobs";
import { validateApiKey } from "@/lib/api-auth";

function authCheck(req: Request): NextResponse | null {
  const denied = validateApiKey(req);
  if (denied) {
    return new NextResponse(denied.body, { status: denied.status, headers: { "Content-Type": "application/json" } });
  }
  return null;
}

export async function GET(req: NextRequest) {
  const denied = authCheck(req);
  if (denied) return denied;
  const jobId = req.nextUrl.searchParams.get("job_id");
  if (!jobId) {
    return NextResponse.json({ error: "job_id required" }, { status: 400 });
  }
  try {
    const result = readJobResult(jobId);
    if (!result) {
      return NextResponse.json({ error: "Report not ready" }, { status: 404 });
    }
    const meta = readJobMeta(jobId);
    appendHistory({
      job_id: jobId,
      repo_name: result.repo_info?.name ?? "Unknown",
      repo_url: meta?.repo_url,
      date: meta?.created_at ?? new Date().toISOString(),
      duration_ms: result.duration_ms ?? 0,
      health_score: result.health_score ?? 0,
      success: result.success ?? false,
      issue_count: result.issues?.length ?? 0,
    });
    return NextResponse.json(result);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Report unavailable" },
      { status: 500 },
    );
  }
}
