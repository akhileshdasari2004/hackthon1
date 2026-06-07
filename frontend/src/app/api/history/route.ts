import { NextRequest, NextResponse } from "next/server";

import { loadHistory, syncHistoryFromJobs } from "@/lib/server/jobs";
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
  try {
    syncHistoryFromJobs();
    return NextResponse.json(loadHistory());
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "History unavailable" },
      { status: 500 },
    );
  }
}
