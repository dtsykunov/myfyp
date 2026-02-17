from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, timezone
from threading import Lock
import time
from typing import Callable


@dataclass(frozen=True)
class AbuseConfig:
    max_snapshot_body_bytes: int = 64 * 1024
    post_requests_per_minute: int = 10
    read_requests_per_minute: int = 120
    write_quota_per_day_per_ip: int = 200

    def __post_init__(self) -> None:
        if self.max_snapshot_body_bytes <= 0:
            raise ValueError("max_snapshot_body_bytes must be positive.")
        if self.post_requests_per_minute <= 0:
            raise ValueError("post_requests_per_minute must be positive.")
        if self.read_requests_per_minute <= 0:
            raise ValueError("read_requests_per_minute must be positive.")
        if self.write_quota_per_day_per_ip <= 0:
            raise ValueError("write_quota_per_day_per_ip must be positive.")


class _FixedWindowLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._time_provider = time_provider or time.time
        self._events: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = self._time_provider()
        with self._lock:
            bucket = self._events.setdefault(key, deque())
            cutoff = now - self._window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._limit:
                return False
            bucket.append(now)
            return True


class _DailyQuotaLimiter:
    def __init__(
        self,
        limit: int,
        date_provider: Callable[[], date] | None = None,
    ) -> None:
        self._limit = limit
        self._date_provider = date_provider or (lambda: datetime.now(timezone.utc).date())
        self._state: dict[str, tuple[date, int]] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        today = self._date_provider()
        with self._lock:
            state = self._state.get(key)
            if state is None or state[0] != today:
                self._state[key] = (today, 1)
                return True

            count = state[1]
            if count >= self._limit:
                return False

            self._state[key] = (today, count + 1)
            return True


class InMemoryAbuseGuard:
    def __init__(
        self,
        config: AbuseConfig,
        time_provider: Callable[[], float] | None = None,
        date_provider: Callable[[], date] | None = None,
    ) -> None:
        self.config = config
        self._post_limiter = _FixedWindowLimiter(
            limit=config.post_requests_per_minute,
            window_seconds=60,
            time_provider=time_provider,
        )
        self._read_limiter = _FixedWindowLimiter(
            limit=config.read_requests_per_minute,
            window_seconds=60,
            time_provider=time_provider,
        )
        self._write_quota = _DailyQuotaLimiter(
            limit=config.write_quota_per_day_per_ip,
            date_provider=date_provider,
        )

    def allow_snapshot_create(self, client_ip: str) -> tuple[bool, str]:
        if not self._post_limiter.allow(client_ip):
            return False, "Rate limit exceeded for snapshot creation."
        if not self._write_quota.allow(client_ip):
            return False, "Daily snapshot creation quota exceeded."
        return True, ""

    def allow_snapshot_read(self, client_ip: str) -> tuple[bool, str]:
        if not self._read_limiter.allow(client_ip):
            return False, "Rate limit exceeded for snapshot retrieval."
        return True, ""

