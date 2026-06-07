import { NextRequest, NextResponse } from "next/server";

import { createJob, readJobStatus, resolveRepoPath } from "@/lib/server/jobs";
import { validateApiKey } from "@/lib/api-auth";
import type { AnalyzeRequest } from "@/types";

function authCheck(req: Request): NextResponse | null {
  const denied = validateApiKey(req);
  if (denied) {
    return new NextResponse(denied.body, { status: denied.status, headers: { "Content-Type": "application/json" } });
  }
  return null;
}

export async function POST(req: NextRequest) {
  const denied = authCheck(req);
  if (denied) return denied;
  try {
    const body = (await req.json()) as AnalyzeRequest;
    const repoPath = resolveRepoPath(body);
    const jobId = createJob(repoPath, body.options);
    return NextResponse.json({ job_id: jobId, status: "queued" });
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Analysis failed" },
      { status: 400 },
    );
  }
}

export async function GET(req: NextRequest) {
  const denied = authCheck(req);
  if (denied) return denied;
  const jobId = req.nextUrl.searchParams.get("job_id");
  if (!jobId) {
    return NextResponse.json({ error: "job_id required" }, { status: 400 });
  }
  try {
    const status = readJobStatus(jobId);
    return NextResponse.json(status);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Status unavailable" },
      { status: 500 },
    );
  }
}
