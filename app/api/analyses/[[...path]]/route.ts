// Hosted deployments must configure the external Python service's origin.
// Local development uses the Vite proxy to port 8000.

// Mirrors the backend's default CODANDY_MAX_UPLOAD_MB; the backend limit is authoritative.
const MAX_ARCHIVE_BYTES = 100 * 1024 * 1024;
const ARCHIVE_TYPES = new Set(["application/zip", "application/x-zip-compressed"]);

async function proxy(request: Request) {
  const origin = process.env.CODANDY_API_URL || process.env.CODE_ATLAS_API_URL;
  if (!origin) return Response.json({ detail: "The analysis backend is not configured for this deployment." }, { status: 503 });
  const incoming = new URL(request.url);
  const path = incoming.pathname;
  if (!/^\/api\/analyses(?:\/archive|\/[0-9a-f-]{36}(?:\/(?:atlas|events|source|dependencies|structure))?)?$/i.test(path)) {
    return Response.json({ detail: "Unknown analysis endpoint" }, { status: 404 });
  }
  const archive = path.toLowerCase() === "/api/analyses/archive";
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
    if (archive) {
      // Only the display file name is forwarded; the body streams through unbuffered.
      const filename = incoming.searchParams.get("filename");
      const type = (request.headers.get("Content-Type") || "").split(";")[0].trim().toLowerCase();
      if (request.method !== "POST") return Response.json({ detail: "Upload archives with POST." }, { status: 405 });
      if (!filename || filename.length > 255) return Response.json({ detail: "A .zip file name is required." }, { status: 400 });
      if (!ARCHIVE_TYPES.has(type)) return Response.json({ detail: "Upload the project as a .zip archive" }, { status: 415 });
      if (Number(request.headers.get("Content-Length")) > MAX_ARCHIVE_BYTES) {
        return Response.json({ detail: "ZIP uploads are limited to 100 MB" }, { status: 413 });
      }
      target.searchParams.set("filename", filename);
    }
    const headers = new Headers();
    headers.set("Content-Type", archive ? "application/zip" : "application/json");
    const lastEvent = request.headers.get("Last-Event-ID");
    if (lastEvent) headers.set("Last-Event-ID", lastEvent);
    const body = request.method !== "POST" ? undefined : archive ? request.body : await request.text();
    const response = await fetch(target, { method: request.method, headers, body,
      redirect: "error", signal: request.signal,
      // Streaming request bodies require half-duplex mode.
      ...(archive ? { duplex: "half" } : {}) } as RequestInit);
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
