import type { Env } from "./types";

const DEFAULT_POST_REQUESTS_PER_MINUTE = 10;
const DEFAULT_READ_REQUESTS_PER_MINUTE = 120;
const DEFAULT_WRITE_QUOTA_PER_DAY_PER_IP = 200;

type AbuseAction = "post" | "read";

export interface AbuseDecision {
  allowed: boolean;
  reason: string;
}

export interface AbuseConfig {
  postRequestsPerMinute: number;
  readRequestsPerMinute: number;
  writeQuotaPerDayPerIp: number;
}

const DEFAULT_CONFIG: AbuseConfig = {
  postRequestsPerMinute: DEFAULT_POST_REQUESTS_PER_MINUTE,
  readRequestsPerMinute: DEFAULT_READ_REQUESTS_PER_MINUTE,
  writeQuotaPerDayPerIp: DEFAULT_WRITE_QUOTA_PER_DAY_PER_IP
};

export async function allowSnapshotCreate(
  env: Env,
  clientIp: string,
  now: Date = new Date(),
  config: AbuseConfig = DEFAULT_CONFIG
): Promise<AbuseDecision> {
  const ipHash = await hashClientIp(clientIp);

  const rateAllowed = await allowRateWindow(
    env,
    ipHash,
    "post",
    config.postRequestsPerMinute,
    now
  );
  if (!rateAllowed) {
    return {
      allowed: false,
      reason: "Rate limit exceeded for snapshot creation."
    };
  }

  const quotaAllowed = await allowDailyWriteQuota(
    env,
    ipHash,
    config.writeQuotaPerDayPerIp,
    now
  );
  if (!quotaAllowed) {
    return {
      allowed: false,
      reason: "Daily snapshot creation quota exceeded."
    };
  }

  return {
    allowed: true,
    reason: ""
  };
}

export async function allowSnapshotRead(
  env: Env,
  clientIp: string,
  now: Date = new Date(),
  config: AbuseConfig = DEFAULT_CONFIG
): Promise<AbuseDecision> {
  const ipHash = await hashClientIp(clientIp);

  const rateAllowed = await allowRateWindow(
    env,
    ipHash,
    "read",
    config.readRequestsPerMinute,
    now
  );
  if (!rateAllowed) {
    return {
      allowed: false,
      reason: "Rate limit exceeded for snapshot retrieval."
    };
  }

  return {
    allowed: true,
    reason: ""
  };
}

async function allowRateWindow(
  env: Env,
  ipHash: string,
  action: AbuseAction,
  limit: number,
  now: Date
): Promise<boolean> {
  const windowStart = toMinuteBucket(now);
  const result = await env.DB.prepare(
    `INSERT INTO abuse_ip_rate_limit (ip_hash, action, window_start, request_count)
     VALUES (?1, ?2, ?3, 1)
     ON CONFLICT(ip_hash, action, window_start)
     DO UPDATE SET request_count = request_count + 1
     WHERE request_count < ?4`
  )
    .bind(ipHash, action, windowStart, limit)
    .run();

  return (result.meta.changes ?? 0) > 0;
}

async function allowDailyWriteQuota(
  env: Env,
  ipHash: string,
  limit: number,
  now: Date
): Promise<boolean> {
  const quotaDate = now.toISOString().slice(0, 10);
  const result = await env.DB.prepare(
    `INSERT INTO abuse_ip_write_daily (ip_hash, quota_date, write_count)
     VALUES (?1, ?2, 1)
     ON CONFLICT(ip_hash, quota_date)
     DO UPDATE SET write_count = write_count + 1
     WHERE write_count < ?3`
  )
    .bind(ipHash, quotaDate, limit)
    .run();

  return (result.meta.changes ?? 0) > 0;
}

function toMinuteBucket(now: Date): string {
  const roundedMs = Math.floor(now.getTime() / 60_000) * 60_000;
  return new Date(roundedMs).toISOString();
}

export async function cleanupAbuseState(env: Env, now: Date = new Date()): Promise<number> {
  const cutoffRateMs = now.getTime() - 2 * 60 * 60 * 1000;
  const cutoffRateIso = new Date(cutoffRateMs).toISOString();
  const cutoffQuotaDate = new Date(now.getTime() - 48 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);

  const rateDeleteResult = await env.DB.prepare(
    "DELETE FROM abuse_ip_rate_limit WHERE window_start < ?1"
  )
    .bind(cutoffRateIso)
    .run();

  const quotaDeleteResult = await env.DB.prepare(
    "DELETE FROM abuse_ip_write_daily WHERE quota_date < ?1"
  )
    .bind(cutoffQuotaDate)
    .run();

  return (rateDeleteResult.meta.changes ?? 0) + (quotaDeleteResult.meta.changes ?? 0);
}

async function hashClientIp(ip: string): Promise<string> {
  const normalized = ip.trim() || "unknown";
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(normalized)
  );
  const bytes = new Uint8Array(digest);
  return Array.from(bytes)
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}
