from __future__ import annotations

from datetime import datetime, timezone


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_snapshot_taken_at(taken_at: datetime) -> str:
    normalized = to_utc(taken_at)
    return normalized.strftime("%Y-%m-%d %H:%M:%S UTC")


def format_relative_time(published_at: datetime, reference_time: datetime) -> str:
    published = to_utc(published_at)
    reference = to_utc(reference_time)
    delta_seconds = max(0, int((reference - published).total_seconds()))
    if delta_seconds <= 0:
        return "just now"

    intervals = (
        ("year", 31_536_000),
        ("month", 2_592_000),
        ("week", 604_800),
        ("day", 86_400),
        ("hour", 3_600),
        ("minute", 60),
        ("second", 1),
    )
    for unit_name, unit_seconds in intervals:
        amount = delta_seconds // unit_seconds
        if amount < 1:
            continue
        suffix = "" if amount == 1 else "s"
        return f"{amount} {unit_name}{suffix} ago"

    return "just now"


def format_compact_views(view_count: int) -> str:
    if view_count < 1_000:
        return f"{view_count} views"
    if view_count < 1_000_000:
        value = view_count / 1_000
        suffix = "K"
    elif view_count < 1_000_000_000:
        value = view_count / 1_000_000
        suffix = "M"
    else:
        value = view_count / 1_000_000_000
        suffix = "B"

    if value >= 10:
        compact_value = f"{value:.0f}"
    else:
        compact_value = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{compact_value}{suffix} views"
