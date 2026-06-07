import { NextRequest, NextResponse } from "next/server";

import { loadSettings, saveSettings } from "@/lib/server/jobs";
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
  return NextResponse.json(loadSettings());
}

export async function PUT(req: NextRequest) {
  const denied = authCheck(req);
  if (denied) return denied;
  try {
    const body = await req.json();
    const settings = saveSettings(body);
    return NextResponse.json(settings);
  } catch (err) {
    return NextResponse.json(
      { error: err instanceof Error ? err.message : "Settings update failed" },
      { status: 400 },
    );
  }
}
