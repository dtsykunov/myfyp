from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
from typing import cast

from for_us_api.abuse import AbuseConfig

from for_us_worker.types import WorkerEnv


@dataclass(frozen=True)
class AbuseDecision:
    allowed: bool
    reason: str = ""


async def allow_snapshot_create(
    env: WorkerEnv,
    client_ip: str,
    now: datetime | None = None,
    config: AbuseConfig | None = None,
) -> AbuseDecision:
    resolved_config = config or AbuseConfig()
    effective_now = _to_utc(now or datetime.now(UTC))
    ip_hash = _hash_ip(client_ip)

    if not await _allow_rate_window(
        env=env,
        ip_hash=ip_hash,
        action="post",
        limit=resolved_config.post_requests_per_minute,
        now=effective_now,
    ):
        return AbuseDecision(False, "Rate limit exceeded for snapshot creation.")

    if not await _allow_daily_write_quota(
        env=env,
        ip_hash=ip_hash,
        limit=resolved_config.write_quota_per_day_per_ip,
        now=effective_now,
    ):
        return AbuseDecision(False, "Daily snapshot creation quota exceeded.")

    return AbuseDecision(True)


async def allow_snapshot_read(
    env: WorkerEnv,
    client_ip: str,
    now: datetime | None = None,
    config: AbuseConfig | None = None,
) -> AbuseDecision:
    resolved_config = config or AbuseConfig()
    effective_now = _to_utc(now or datetime.now(UTC))
    ip_hash = _hash_ip(client_ip)

    if not await _allow_rate_window(
        env=env,
        ip_hash=ip_hash,
        action="read",
        limit=resolved_config.read_requests_per_minute,
        now=effective_now,
    ):
        return AbuseDecision(False, "Rate limit exceeded for snapshot retrieval.")

    return AbuseDecision(True)


async def cleanup_abuse_state(env: WorkerEnv, now: datetime | None = None) -> int:
    effective_now = _to_utc(now or datetime.now(UTC))
    rate_cutoff = effective_now - timedelta(hours=2)
    quota_cutoff = (effective_now - timedelta(hours=48)).date().isoformat()

    rate_result = await env.DB.prepare(
        """
        DELETE FROM abuse_ip_rate_limit
        WHERE window_start < ?
        """
    ).bind(rate_cutoff.isoformat()).run()
    quota_result = await env.DB.prepare(
        """
        DELETE FROM abuse_ip_write_daily
        WHERE quota_date < ?
        """
    ).bind(quota_cutoff).run()

    return _extract_changes(rate_result) + _extract_changes(quota_result)


async def _allow_rate_window(
    env: WorkerEnv,
    ip_hash: str,
    action: str,
    limit: int,
    now: datetime,
) -> bool:
    window_start = now.replace(second=0, microsecond=0).isoformat()
    result = await env.DB.prepare(
        """
        INSERT INTO abuse_ip_rate_limit (ip_hash, action, window_start, request_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(ip_hash, action, window_start)
        DO UPDATE SET request_count = request_count + 1
        WHERE request_count < ?
        """
    ).bind(ip_hash, action, window_start, limit).run()
    return _extract_changes(result) > 0


async def _allow_daily_write_quota(
    env: WorkerEnv,
    ip_hash: str,
    limit: int,
    now: datetime,
) -> bool:
    quota_date = now.date().isoformat()
    result = await env.DB.prepare(
        """
        INSERT INTO abuse_ip_write_daily (ip_hash, quota_date, write_count)
        VALUES (?, ?, 1)
        ON CONFLICT(ip_hash, quota_date)
        DO UPDATE SET write_count = write_count + 1
        WHERE write_count < ?
        """
    ).bind(ip_hash, quota_date, limit).run()
    return _extract_changes(result) > 0


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _hash_ip(client_ip: str) -> str:
    normalized = client_ip.strip() or "unknown"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _extract_changes(result: object) -> int:
    if isinstance(result, Mapping):
        result_mapping = cast(Mapping[str, object], result)
        meta = result_mapping.get("meta")
        if isinstance(meta, Mapping):
            meta_mapping = cast(Mapping[str, object], meta)
            changes = meta_mapping.get("changes")
            if isinstance(changes, int):
                return changes
    return 0
