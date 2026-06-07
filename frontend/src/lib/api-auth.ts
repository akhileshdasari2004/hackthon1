/**
 * API key authentication middleware.
 * Reads API_KEY from environment and validates X-API-Key header.
 */

const API_KEY = process.env.API_KEY ?? "";

export function validateApiKey(request: Request): Response | null {
  // Skip auth if no API_KEY is configured (development mode)
  if (!API_KEY) return null;

  const key = request.headers.get("X-API-Key");
  if (!key || key !== API_KEY) {
    return new Response(
      JSON.stringify({ error: "Unauthorized", message: "Invalid or missing X-API-Key" }),
      { status: 401, headers: { "Content-Type": "application/json" } },
    );
  }
  return null;
}

export function requireApiKey(handler: (req: Request) => Promise<Response>): (req: Request) => Promise<Response> {
  return async (req: Request) => {
    const denied = validateApiKey(req);
    if (denied) return denied;
    return handler(req);
  };
}