import { createExecutionContext, env, waitOnExecutionContext } from "cloudflare:test";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";

import worker from "../src/index";

const SCHEMA_SQL = `
CREATE TABLE IF NOT EXISTS snapshots (
  hash TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_expires_at
ON snapshots (expires_at);

CREATE TABLE IF NOT EXISTS abuse_ip_write_daily (
  ip_hash TEXT NOT NULL,
  quota_date TEXT NOT NULL,
  write_count INTEGER NOT NULL,
  PRIMARY KEY (ip_hash, quota_date)
);

CREATE TABLE IF NOT EXISTS abuse_ip_rate_limit (
  ip_hash TEXT NOT NULL,
  action TEXT NOT NULL,
  window_start TEXT NOT NULL,
  request_count INTEGER NOT NULL,
  PRIMARY KEY (ip_hash, action, window_start)
);
`;

beforeAll(async () => {
  await env.DB.exec(SCHEMA_SQL);
});

beforeEach(async () => {
  await env.DB.exec("DELETE FROM snapshots;");
  await env.DB.exec("DELETE FROM abuse_ip_write_daily;");
  await env.DB.exec("DELETE FROM abuse_ip_rate_limit;");
});

describe("snapshot API", () => {
  it("creates and retrieves a snapshot", async () => {
    const createRequest = new Request("https://example.com/api/snapshots", {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        capturedAt: "2026-02-17T11:00:00Z",
        pageUrl: "https://www.youtube.com/",
        videos: [
          {
            videoHash: "lzChIIJMpGk",
            title: "deadlock: items for idiot",
            channelName: "chalant",
            channelLink: "https://www.youtube.com/@itschalant",
            channelAvatar: "https://yt3.ggpht.com/avatar",
            publishedAt: "2026-02-14T11:00:00Z",
            viewCount: 81000
          }
        ],
        shorts: [{ videoHash: "dQw4w9WgXcQ", title: "short" }]
      })
    });

    const createCtx = createExecutionContext();
    const createResponse = await worker.fetch(createRequest, env, createCtx);
    await waitOnExecutionContext(createCtx);

    expect(createResponse.status).toBe(201);
    const createBody = (await createResponse.json()) as { hash: string; expiresAt: string };
    expect(createBody.hash).toHaveLength(12);
    expect(Date.parse(createBody.expiresAt)).not.toBeNaN();

    const getRequest = new Request(`https://example.com/api/snapshots/${createBody.hash}`, {
      method: "GET"
    });
    const getCtx = createExecutionContext();
    const getResponse = await worker.fetch(getRequest, env, getCtx);
    await waitOnExecutionContext(getCtx);

    expect(getResponse.status).toBe(200);
    expect(getResponse.headers.get("etag")).toBe(`"api-${createBody.hash}"`);
    expect(getResponse.headers.get("cache-control")).toContain("max-age=");

    const payload = await getResponse.json();
    expect(payload).toEqual({
      capturedAt: "2026-02-17T11:00:00.000Z",
      pageUrl: "https://www.youtube.com/",
      videos: [
        {
          videoHash: "lzChIIJMpGk",
          title: "deadlock: items for idiot",
          channelName: "chalant",
          channelLink: "https://www.youtube.com/@itschalant",
          channelAvatar: "https://yt3.ggpht.com/avatar",
          publishedAt: "2026-02-14T11:00:00.000Z",
          viewCount: 81000
        }
      ],
      shorts: [{ videoHash: "dQw4w9WgXcQ", title: "short" }]
    });
  });

  it("returns 304 when If-None-Match matches", async () => {
    const createRequest = new Request("https://example.com/api/snapshots", {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        videos: [{ videoHash: "lzChIIJMpGk", title: "title" }],
        shorts: []
      })
    });

    const createCtx = createExecutionContext();
    const createResponse = await worker.fetch(createRequest, env, createCtx);
    await waitOnExecutionContext(createCtx);
    const createBody = (await createResponse.json()) as { hash: string };

    const getRequest = new Request(`https://example.com/api/snapshots/${createBody.hash}`, {
      method: "GET",
      headers: {
        "if-none-match": `"api-${createBody.hash}"`
      }
    });
    const getCtx = createExecutionContext();
    const getResponse = await worker.fetch(getRequest, env, getCtx);
    await waitOnExecutionContext(getCtx);

    expect(getResponse.status).toBe(304);
  });

  it("rejects invalid payload", async () => {
    const request = new Request("https://example.com/api/snapshots", {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        videos: [{ videoHash: "invalid", title: "bad" }],
        shorts: []
      })
    });

    const ctx = createExecutionContext();
    const response = await worker.fetch(request, env, ctx);
    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(422);
  });

  it("returns 410 for expired snapshots", async () => {
    const snapshotHash = "Ab12Cd34Ef56";
    await env.DB.prepare(
      `INSERT INTO snapshots (hash, created_at, expires_at, payload_json)
       VALUES (?1, ?2, ?3, ?4)`
    )
      .bind(
        snapshotHash,
        "2026-02-01T00:00:00.000Z",
        "2026-02-02T00:00:00.000Z",
        JSON.stringify({ videos: [], shorts: [] })
      )
      .run();

    const request = new Request(`https://example.com/api/snapshots/${snapshotHash}`, {
      method: "GET"
    });
    const ctx = createExecutionContext();
    const response = await worker.fetch(request, env, ctx);
    await waitOnExecutionContext(ctx);

    expect(response.status).toBe(410);

    const countResult = await env.DB.prepare("SELECT COUNT(*) AS count FROM snapshots WHERE hash = ?1")
      .bind(snapshotHash)
      .first<{ count: number }>();
    expect(countResult?.count ?? 0).toBe(0);
  });
});
