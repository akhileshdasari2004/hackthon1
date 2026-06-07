import { existsSync, readFileSync } from "fs";
import { NextRequest, NextResponse } from "next/server";

import { MEMORY_STORE_PATH } from "@/lib/config";
import { validateApiKey } from "@/lib/api-auth";
import type { MemoryData } from "@/types";

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
    if (!existsSync(MEMORY_STORE_PATH)) {
      return NextResponse.json({
        failures: {},
        successes: {},
        repo_profiles: {},
        tool_metrics: {},
        learning_log: [],
      } satisfies MemoryData);
    }
    const raw = JSON.parse(readFileSync(MEMORY_STORE_PATH, "utf-8"));
    const data: MemoryData = {
      failures: raw.failures ?? {},
      successes: raw.successes ?? {},
      repo_profiles: raw.repo_profiles ?? {},
      tool_metrics: raw.tool_metrics ?? {},
      learning_log: raw.learning_log ?? [],
    };
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Memory unavailable" },
      { status: 500 },
    );
  }
}
