// Hosted deployments must configure the external Python service's origin.
// Local development uses the Vite proxy to port 8000.
async function proxy(request: Request) {
  const origin = process.env.CODANDY_API_URL || process.env.CODE_ATLAS_API_URL;
  if (!origin) return Response.json({ detail: "The analysis backend is not configured for this deployment." }, { status: 503 });
  const incoming = new URL(request.url);
  const path = incoming.pathname;
  if (!/^\/api\/analyses(?:\/[0-9a-f-]{36}(?:\/(?:atlas|events|source|dependencies))?)?$/i.test(path)) {
    return Response.json({ detail: "Unknown analysis endpoint" }, { status: 404 });
  }
  try {
    const target = new URL(origin);
    if (target.protocol !== "https:" || target.username || target.password || target.search || target.hash) {
      return Response.json({ detail: "The analysis backend configuration is invalid." }, { status: 503 });
    }
    target.pathname = path;
    if (path.toLowerCase().endsWith("/dependencies")) {
      const nodeId = incoming.searchParams.get("node_id");
      if (!nodeId || nodeId.length > 200) return Response.json({ detail: "A dependency node is required." }, { status: 400 });
      target.searchParams.set("node_id", nodeId);
    }
    if (path.toLowerCase().endsWith("/source")) {
      // Only this one query parameter is forwarded, never the whole query string.
      const sourcePath = incoming.searchParams.get("path");
      if (!sourcePath || sourcePath.length > 1024) {
        return Response.json({ detail: "A source path is required." }, { status: 400 });
      }
      target.searchParams.set("path", sourcePath);
    }
    const headers = new Headers();
    headers.set("Content-Type", "application/json");
    const lastEvent = request.headers.get("Last-Event-ID");
    if (lastEvent) headers.set("Last-Event-ID", lastEvent);
    const response = await fetch(target, { method: request.method, headers,
      body: request.method === "POST" ? await request.text() : undefined,
      redirect: "error", signal: request.signal });
    const outgoing = new Headers({ "Cache-Control": "no-store", "X-Accel-Buffering": "no" });
    for (const name of ["Content-Type", "Retry-After"]) {
      const value = response.headers.get(name); if (value) outgoing.set(name, value);
    }
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return Response.json({ detail: "The analysis backend is unavailable. Please retry." }, { status: 502 });
  }
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
