import {
  MAX_HASH_GENERATION_ATTEMPTS,
  RETENTION_DAYS
} from "./constants";
import { generateSnapshotHash } from "./hash";
import type { Env, SnapshotPayload, StoredSnapshotRecord } from "./types";

interface DbSnapshotRow {
  hash: string;
  created_at: string;
  expires_at: string;
  payload_json: string;
}

export interface GetSnapshotResult {
  snapshot: StoredSnapshotRecord | null;
  isExpired: boolean;
}

export async function createSnapshot(env: Env, payload: SnapshotPayload, now: Date = new Date()): Promise<StoredSnapshotRecord> {
  const createdAt = now.toISOString();
  const expiresAt = new Date(now.getTime() + RETENTION_DAYS * 24 * 60 * 60 * 1000).toISOString();
  const payloadJson = JSON.stringify(payload);

  for (let attempt = 0; attempt < MAX_HASH_GENERATION_ATTEMPTS; attempt += 1) {
    const hash = generateSnapshotHash();
    const inserted = await tryInsertSnapshot(env, hash, createdAt, expiresAt, payloadJson);
    if (inserted) {
      return {
        hash,
        createdAt,
        expiresAt,
        payload
      };
    }
  }

  throw new Error("Unable to persist snapshot due to hash collisions.");
}

async function tryInsertSnapshot(
  env: Env,
  hash: string,
  createdAt: string,
  expiresAt: string,
  payloadJson: string
): Promise<boolean> {
  const query = env.DB.prepare(
    `INSERT OR IGNORE INTO snapshots (hash, created_at, expires_at, payload_json)
     VALUES (?1, ?2, ?3, ?4)`
  );
  const result = await query.bind(hash, createdAt, expiresAt, payloadJson).run();
  return (result.meta.changes ?? 0) > 0;
}

export async function getSnapshotByHash(
  env: Env,
  hash: string,
  now: Date = new Date()
): Promise<GetSnapshotResult> {
  const query = env.DB.prepare(
    `SELECT hash, created_at, expires_at, payload_json
     FROM snapshots
     WHERE hash = ?1`
  );
  const row = await query.bind(hash).first<DbSnapshotRow>();
  if (!row) {
    return { snapshot: null, isExpired: false };
  }

  if (Date.parse(row.expires_at) <= now.getTime()) {
    await deleteSnapshotByHash(env, hash);
    return { snapshot: null, isExpired: true };
  }

  const payload = JSON.parse(row.payload_json) as SnapshotPayload;
  return {
    snapshot: {
      hash: row.hash,
      createdAt: row.created_at,
      expiresAt: row.expires_at,
      payload
    },
    isExpired: false
  };
}

export async function deleteSnapshotByHash(env: Env, hash: string): Promise<void> {
  await env.DB.prepare("DELETE FROM snapshots WHERE hash = ?1").bind(hash).run();
}

export async function deleteExpiredSnapshots(env: Env, now: Date = new Date()): Promise<number> {
  const result = await env.DB.prepare("DELETE FROM snapshots WHERE expires_at <= ?1")
    .bind(now.toISOString())
    .run();
  return result.meta.changes ?? 0;
}
