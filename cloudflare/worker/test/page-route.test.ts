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
`;

beforeAll(async () => {
  await env.DB.exec(SCHEMA_SQL);
});

beforeEach(async () => {
  await env.DB.exec("DELETE FROM snapshots;");
  await env.DB.exec("DELETE FROM abuse_ip_write_daily;");
});

describe("snapshot HTML page route", () => {
  it("renders snapshot HTML from hash route", async () => {
    const createRequest = new Request("https://example.com/api/snapshots", {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify({
        capturedAt: "2026-02-17T11:00:00Z",
        pageUrl: "https://www.youtube.com/",
        videos: [{ videoHash: "lzChIIJMpGk", title: "deadlock: items for idiot" }],
        shorts: [{ videoHash: "dQw4w9WgXcQ", title: "short item" }]
      })
    });

    const createCtx = createExecutionContext();
    const createResponse = await worker.fetch(createRequest, env, createCtx);
    await waitOnExecutionContext(createCtx);
    const createBody = (await createResponse.json()) as { hash: string };

    const pageRequest = new Request(`https://example.com/${createBody.hash}`, {
      method: "GET"
    });
    const pageCtx = createExecutionContext();
    const pageResponse = await worker.fetch(pageRequest, env, pageCtx);
    await waitOnExecutionContext(pageCtx);

    expect(pageResponse.status).toBe(200);
    expect(pageResponse.headers.get("etag")).toBe(`"html-${createBody.hash}"`);
    expect(pageResponse.headers.get("content-type")).toContain("text/html");

    const html = await pageResponse.text();
    expect(html).toContain("For Us Page by");
    expect(html).toContain("A snapshot of a personal YouTube recommendation page.");
    expect(html).toContain("Snapshot hash:");
    expect(html).toContain("Videos");
    expect(html).toContain("Shorts");
    expect(html).toContain("FAQ");
  });

  it("returns 304 for matching page etag", async () => {
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

    const pageRequest = new Request(`https://example.com/${createBody.hash}`, {
      method: "GET",
      headers: {
        "if-none-match": `"html-${createBody.hash}"`
      }
    });

    const pageCtx = createExecutionContext();
    const pageResponse = await worker.fetch(pageRequest, env, pageCtx);
    await waitOnExecutionContext(pageCtx);

    expect(pageResponse.status).toBe(304);
  });
});
