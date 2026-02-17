import { MAX_SNAPSHOT_BODY_BYTES, SNAPSHOT_HASH_PATTERN } from "./constants";
import { HttpError } from "./errors";
import {
  buildCacheHeaders,
  buildEtag,
  ifNoneMatchMatches,
  jsonError,
  jsonResponse,
  parseJsonBodyWithSizeLimit
} from "./http";
import { parseSnapshotPayload } from "./payload";
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
  }
};
