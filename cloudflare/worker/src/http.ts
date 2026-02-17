import { HttpError } from "./errors";

export function jsonResponse(body: unknown, status = 200, headers?: HeadersInit): Response {
  const resolvedHeaders = new Headers(headers);
  if (!resolvedHeaders.has("content-type")) {
    resolvedHeaders.set("content-type", "application/json; charset=utf-8");
  }

  return new Response(JSON.stringify(body), {
    status,
    headers: resolvedHeaders
  });
}

export function jsonError(status: number, detail: string): Response {
  return jsonResponse({ detail }, status);
}

export function buildEtag(prefix: "api" | "html", snapshotHash: string): string {
  return `"${prefix}-${snapshotHash}"`;
}

export function buildCacheHeaders(expiresAtIso: string, etag: string, now: Date = new Date()): Headers {
  const expiresAtMs = Date.parse(expiresAtIso);
  const maxAge = Number.isNaN(expiresAtMs)
    ? 0
    : Math.max(0, Math.floor((expiresAtMs - now.getTime()) / 1000));
  const headers = new Headers();
  headers.set("cache-control", `public, max-age=${maxAge}, immutable`);
  headers.set("etag", etag);
  return headers;
}

export function ifNoneMatchMatches(ifNoneMatchHeader: string | null, expectedEtag: string): boolean {
  if (ifNoneMatchHeader === null) {
    return false;
  }

  const trimmed = ifNoneMatchHeader.trim();
  if (trimmed === "*") {
    return true;
  }

  return trimmed.split(",").map((token) => token.trim()).includes(expectedEtag);
}

export function getClientIp(request: Request): string {
  const cfConnectingIp = request.headers.get("cf-connecting-ip");
  if (cfConnectingIp) {
    return cfConnectingIp.trim();
  }
  const forwardedFor = request.headers.get("x-forwarded-for");
  if (forwardedFor) {
    return forwardedFor.split(",")[0]?.trim() ?? "unknown";
  }
  return "unknown";
}

export async function parseJsonBodyWithSizeLimit(request: Request, maxBytes: number): Promise<unknown> {
  const contentLength = request.headers.get("content-length");
  if (contentLength !== null) {
    const parsedLength = Number.parseInt(contentLength, 10);
    if (Number.isNaN(parsedLength)) {
      throw new HttpError(400, "Invalid Content-Length header.");
    }
    if (parsedLength > maxBytes) {
      throw new HttpError(413, "Request body too large.");
    }
  }

  const bodyText = await request.text();
  const bodySize = new TextEncoder().encode(bodyText).byteLength;
  if (bodySize > maxBytes) {
    throw new HttpError(413, "Request body too large.");
  }

  try {
    return JSON.parse(bodyText) as unknown;
  } catch {
    throw new HttpError(400, "Request body must be valid JSON.");
  }
}
