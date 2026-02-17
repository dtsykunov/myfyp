import { env } from "cloudflare:test";
import { beforeAll, beforeEach, describe, expect, it } from "vitest";

import { allowSnapshotCreate, allowSnapshotRead, cleanupAbuseState } from "../src/abuse";

const SCHEMA_SQL = `
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
  await env.DB.exec("DELETE FROM abuse_ip_write_daily;");
  await env.DB.exec("DELETE FROM abuse_ip_rate_limit;");
});

describe("d1 abuse guard", () => {
  it("enforces per-minute create rate limit", async () => {
    const now = new Date("2026-02-17T11:00:00.000Z");
    const config = {
      postRequestsPerMinute: 2,
      readRequestsPerMinute: 10,
      writeQuotaPerDayPerIp: 10
    };

    const first = await allowSnapshotCreate(env, "203.0.113.10", now, config);
    const second = await allowSnapshotCreate(env, "203.0.113.10", now, config);
    const third = await allowSnapshotCreate(env, "203.0.113.10", now, config);

    expect(first.allowed).toBe(true);
    expect(second.allowed).toBe(true);
    expect(third.allowed).toBe(false);
    expect(third.reason).toBe("Rate limit exceeded for snapshot creation.");
  });

  it("enforces daily create quota", async () => {
    const now = new Date("2026-02-17T11:00:00.000Z");
    const config = {
      postRequestsPerMinute: 10,
      readRequestsPerMinute: 10,
      writeQuotaPerDayPerIp: 2
    };

    const first = await allowSnapshotCreate(env, "203.0.113.11", now, config);
    const second = await allowSnapshotCreate(env, "203.0.113.11", now, config);
    const third = await allowSnapshotCreate(env, "203.0.113.11", now, config);

    expect(first.allowed).toBe(true);
    expect(second.allowed).toBe(true);
    expect(third.allowed).toBe(false);
    expect(third.reason).toBe("Daily snapshot creation quota exceeded.");
  });

  it("enforces per-minute read rate limit", async () => {
    const now = new Date("2026-02-17T11:00:00.000Z");
    const config = {
      postRequestsPerMinute: 10,
      readRequestsPerMinute: 2,
      writeQuotaPerDayPerIp: 10
    };

    const first = await allowSnapshotRead(env, "203.0.113.12", now, config);
    const second = await allowSnapshotRead(env, "203.0.113.12", now, config);
    const third = await allowSnapshotRead(env, "203.0.113.12", now, config);

    expect(first.allowed).toBe(true);
    expect(second.allowed).toBe(true);
    expect(third.allowed).toBe(false);
    expect(third.reason).toBe("Rate limit exceeded for snapshot retrieval.");
  });

  it("cleans up old abuse rows", async () => {
    await env.DB.prepare(
      `INSERT INTO abuse_ip_rate_limit (ip_hash, action, window_start, request_count)
       VALUES (?1, ?2, ?3, ?4)`
    )
      .bind("old", "post", "2026-02-15T00:00:00.000Z", 1)
      .run();

    await env.DB.prepare(
      `INSERT INTO abuse_ip_write_daily (ip_hash, quota_date, write_count)
       VALUES (?1, ?2, ?3)`
    )
      .bind("old", "2026-02-15", 1)
      .run();

    const deleted = await cleanupAbuseState(env, new Date("2026-02-17T12:00:00.000Z"));
    expect(deleted).toBeGreaterThanOrEqual(2);
  });
});
