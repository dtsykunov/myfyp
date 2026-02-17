import { allowSnapshotCreate, allowSnapshotRead, cleanupAbuseState } from "./abuse";
import { MAX_SNAPSHOT_BODY_BYTES, SNAPSHOT_HASH_PATTERN } from "./constants";
import { HttpError } from "./errors";
import {
  buildCacheHeaders,
  buildEtag,
  getClientIp,
  ifNoneMatchMatches,
  jsonError,
  jsonResponse,
  parseJsonBodyWithSizeLimit
} from "./http";
import { parseSnapshotPayload } from "./payload";
import { renderSnapshotHtml } from "./render";
import { createSnapshot, deleteExpiredSnapshots, getSnapshotByHash } from "./store";
import type { Env } from "./types";

function isSnapshotApiPath(pathname: string): boolean {
  return pathname.startsWith("/api/snapshots/") && pathname.length > "/api/snapshots/".length;
}

function parseSnapshotHashFromPath(pathname: string): string {
  const hash = pathname.slice("/api/snapshots/".length);
  return hash;
}

async function handleCreateSnapshot(request: Request, env: Env): Promise<Response> {
  const createDecision = await allowSnapshotCreate(env, getClientIp(request));
  if (!createDecision.allowed) {
    return jsonError(429, createDecision.reason);
  }

  const body = await parseJsonBodyWithSizeLimit(request, MAX_SNAPSHOT_BODY_BYTES);
  const payload = parseSnapshotPayload(body);
  const snapshot = await createSnapshot(env, payload);

  return jsonResponse(
    {
      hash: snapshot.hash,
      expiresAt: snapshot.expiresAt
    },
    201
  );
}

async function handleGetSnapshot(request: Request, env: Env, snapshotHash: string): Promise<Response> {
  const readDecision = await allowSnapshotRead(env, getClientIp(request));
  if (!readDecision.allowed) {
    return jsonError(429, readDecision.reason);
  }

  const snapshotResult = await getSnapshotByHash(env, snapshotHash);
  if (snapshotResult.isExpired) {
    return jsonError(410, "Snapshot has expired.");
  }
  if (snapshotResult.snapshot === null) {
    return jsonError(404, "Snapshot not found.");
  }

  const etag = buildEtag("api", snapshotResult.snapshot.hash);
  const headers = buildCacheHeaders(snapshotResult.snapshot.expiresAt, etag);
  if (ifNoneMatchMatches(request.headers.get("if-none-match"), etag)) {
    return new Response(null, {
      status: 304,
      headers
    });
  }

  return jsonResponse(snapshotResult.snapshot.payload, 200, headers);
}

async function handleRenderSnapshotPage(request: Request, env: Env, snapshotHash: string): Promise<Response> {
  const readDecision = await allowSnapshotRead(env, getClientIp(request));
  if (!readDecision.allowed) {
    return new Response("<h1>429 Too Many Requests</h1>", {
      status: 429,
      headers: {
        "content-type": "text/html; charset=utf-8"
      }
    });
  }

  const snapshotResult = await getSnapshotByHash(env, snapshotHash);
  if (snapshotResult.isExpired) {
    return new Response("<h1>410 Snapshot expired</h1>", {
      status: 410,
      headers: {
        "content-type": "text/html; charset=utf-8"
      }
    });
  }
  if (snapshotResult.snapshot === null) {
    return new Response("<h1>404 Snapshot not found</h1>", {
      status: 404,
      headers: {
        "content-type": "text/html; charset=utf-8"
      }
    });
  }

  const etag = buildEtag("html", snapshotResult.snapshot.hash);
  const headers = buildCacheHeaders(snapshotResult.snapshot.expiresAt, etag);
  headers.set("content-type", "text/html; charset=utf-8");

  if (ifNoneMatchMatches(request.headers.get("if-none-match"), etag)) {
    return new Response(null, {
      status: 304,
      headers
    });
  }

  return new Response(renderSnapshotHtml(snapshotResult.snapshot), {
    status: 200,
    headers
  });
}

async function handleRequest(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);

  if (request.method === "GET" && url.pathname === "/health") {
    return jsonResponse({ status: "ok" });
  }

  if (request.method === "POST" && url.pathname === "/api/snapshots") {
    return handleCreateSnapshot(request, env);
  }

  if (request.method === "GET" && isSnapshotApiPath(url.pathname)) {
    const snapshotHash = parseSnapshotHashFromPath(url.pathname);
    if (!SNAPSHOT_HASH_PATTERN.test(snapshotHash)) {
      return jsonError(404, "Snapshot not found.");
    }
    return handleGetSnapshot(request, env, snapshotHash);
  }

  if (request.method === "GET" && SNAPSHOT_HASH_PATTERN.test(url.pathname.slice(1))) {
    return handleRenderSnapshotPage(request, env, url.pathname.slice(1));
  }

  return jsonError(501, "Worker scaffold is ready. Endpoint implementation is in progress.");
}

export default {
  async fetch(request: Request, env: Env, _ctx: ExecutionContext): Promise<Response> {
    try {
      return await handleRequest(request, env);
    } catch (error) {
      if (error instanceof HttpError) {
        return jsonError(error.status, error.detail);
      }

      return jsonError(500, "Internal server error.");
    }
  },

  async scheduled(_event: ScheduledEvent, env: Env, _ctx: ExecutionContext): Promise<void> {
    await deleteExpiredSnapshots(env);
    await cleanupAbuseState(env);
  }
};
