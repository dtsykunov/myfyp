from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import html

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import Response

from for_us_api.abuse import AbuseConfig, InMemoryAbuseGuard
from for_us_api.models import CreateSnapshotRequest, CreateSnapshotResponse, RecommendationItem, StoredSnapshot
from for_us_api.store import SnapshotStore


def create_app(
    store: SnapshotStore | None = None,
    abuse_guard: InMemoryAbuseGuard | None = None,
) -> FastAPI:
    """Create and configure the API application."""
    snapshot_store = store or SnapshotStore.from_environment()
    guard = abuse_guard or InMemoryAbuseGuard(AbuseConfig())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        snapshot_store.initialize()
        yield

    app = FastAPI(title="For Us API", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def enforce_snapshot_body_size(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:  # pyright: ignore[reportUnusedFunction]
        if request.method == "POST" and request.url.path == "/api/snapshots":
            content_length = request.headers.get("content-length")
            if content_length is not None:
                try:
                    parsed_length = int(content_length)
                except ValueError:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Invalid Content-Length header."},
                    )
                if parsed_length > guard.config.max_snapshot_body_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Request body too large."},
                    )

            body = await request.body()
            if len(body) > guard.config.max_snapshot_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large."},
                )
        return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    @app.post("/api/snapshots", status_code=201, response_model=CreateSnapshotResponse)
    def create_snapshot(request: Request, payload: CreateSnapshotRequest) -> CreateSnapshotResponse:  # pyright: ignore[reportUnusedFunction]
        allowed, reason = guard.allow_snapshot_create(_client_ip(request))
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)
        return snapshot_store.create_snapshot(payload)

    @app.get(
        "/api/snapshots/{snapshot_hash}",
        response_model=CreateSnapshotRequest,
        response_model_exclude_none=True,
    )
    def get_snapshot(request: Request, snapshot_hash: str) -> CreateSnapshotRequest:  # pyright: ignore[reportUnusedFunction]
        allowed, reason = guard.allow_snapshot_read(_client_ip(request))
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)
        snapshot, is_expired = snapshot_store.get_snapshot(snapshot_hash)
        if is_expired:
            raise HTTPException(status_code=410, detail="Snapshot has expired.")
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot not found.")
        return snapshot.payload

    @app.get("/{snapshot_hash}", response_class=HTMLResponse)
    def render_snapshot_page(request: Request, snapshot_hash: str) -> HTMLResponse:  # pyright: ignore[reportUnusedFunction]
        allowed, _reason = guard.allow_snapshot_read(_client_ip(request))
        if not allowed:
            return HTMLResponse("<h1>429 Too Many Requests</h1>", status_code=429)
        snapshot, is_expired = snapshot_store.get_snapshot(snapshot_hash)
        if is_expired:
            return HTMLResponse("<h1>410 Snapshot expired</h1>", status_code=410)
        if snapshot is None:
            return HTMLResponse("<h1>404 Snapshot not found</h1>", status_code=404)
        return HTMLResponse(_render_snapshot_html(snapshot), status_code=200)

    return app


app = create_app()


def _render_snapshot_html(snapshot: StoredSnapshot) -> str:
    metadata_reference_time = _resolve_metadata_reference_time(snapshot)
    videos = _render_video_grid(snapshot.payload.videos, metadata_reference_time)
    shorts = _render_shorts_grid(snapshot.payload.shorts, metadata_reference_time)
    escaped_hash = html.escape(snapshot.hash)
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>For Us Page - {escaped_hash}</title>
    <style>
      :root {{
        --bg: #0f0f0f;
        --card: #181818;
        --text: #f1f1f1;
        --muted: #aaaaaa;
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: Arial, sans-serif;
      }}

      main {{
        max-width: 2400px;
        margin: 0 auto;
        padding: 20px;
      }}

      h1 {{
        margin: 0 0 8px;
        font-size: 28px;
      }}

      .meta {{
        margin: 0 0 24px;
        color: var(--muted);
      }}

      .section-title {{
        margin: 24px 0 12px;
        font-size: 22px;
      }}

      .videos-grid {{
        display: grid;
        grid-template-columns: repeat(6, 365px);
        gap: 16px;
        justify-content: center;
      }}

      .shorts-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, 365px);
        gap: 16px;
        justify-content: center;
      }}

      .video-card {{
        width: 365px;
        height: 305px;
        background: var(--card);
        border-radius: 14px;
        overflow: hidden;
        position: relative;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition:
          transform 300ms cubic-bezier(0.4, 0, 0.2, 1),
          box-shadow 300ms cubic-bezier(0.4, 0, 0.2, 1),
          background 300ms cubic-bezier(0.4, 0, 0.2, 1),
          opacity 300ms cubic-bezier(0.4, 0, 0.2, 1);
      }}

      .video-card:hover {{
        transform: translateY(-6px);
        box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
        background: #202020;
      }}

      .short-card {{
        width: 365px;
        height: 547px;
        background: var(--card);
        border-radius: 10px;
        overflow: hidden;
      }}

      .thumb {{
        display: block;
      }}

      .video-card .thumb {{
        position: absolute;
        top: 0;
        left: 0;
        width: 365px;
        height: 205px;
        overflow: hidden;
      }}

      .video-card .thumb img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
        transform: scale(1);
        transition: transform 300ms ease;
      }}

      .video-card:hover .thumb img {{
        transform: scale(1.05);
      }}

      .video-card .image-overlay {{
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0);
        transition: background 300ms cubic-bezier(0.4, 0, 0.2, 1);
      }}

      .video-card:hover .image-overlay {{
        background: linear-gradient(
          to bottom,
          rgba(0, 0, 0, 0) 20%,
          rgba(0, 0, 0, 0.45) 70%,
          rgba(0, 0, 0, 0.6) 100%
        );
      }}

      .video-card .play-icon {{
        position: absolute;
        top: 50%;
        left: 50%;
        width: 52px;
        height: 52px;
        margin-left: -26px;
        margin-top: -26px;
        border-radius: 999px;
        background: rgba(0, 0, 0, 0.55);
        color: #fff;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 20px;
        transform: scale(0.9);
        opacity: 0;
        transition:
          opacity 260ms cubic-bezier(0.4, 0, 0.2, 1),
          transform 260ms cubic-bezier(0.4, 0, 0.2, 1);
      }}

      .video-card:hover .play-icon {{
        opacity: 1;
        transform: scale(1);
      }}

      .short-card .thumb img {{
        width: 365px;
        height: 487px;
        object-fit: cover;
        display: block;
      }}

      .title {{
        margin: 0;
        font-size: 14px;
        line-height: 1.25;
        color: var(--text);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }}

      .empty {{
        color: var(--muted);
      }}

      .short-card .card-body {{
        padding: 10px 12px;
      }}

      .video-card .card-body {{
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        min-height: 100px;
        padding: 10px 12px;
        background: linear-gradient(180deg, rgba(24, 24, 24, 0.9) 0%, rgba(24, 24, 24, 0.98) 100%);
        transform: translateY(6px);
        transition:
          transform 300ms cubic-bezier(0.4, 0, 0.2, 1),
          filter 300ms cubic-bezier(0.4, 0, 0.2, 1);
      }}

      .video-card:hover .card-body {{
        transform: translateY(0);
        filter: brightness(1.06);
      }}

      .meta-line {{
        margin-top: 6px;
        color: var(--muted);
        font-size: 12px;
        line-height: 1.25;
      }}

      .channel {{
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 8px;
      }}

      .channel-avatar {{
        width: 22px;
        height: 22px;
        border-radius: 999px;
        object-fit: cover;
        flex-shrink: 0;
      }}

      .channel-avatar-placeholder {{
        width: 22px;
        height: 22px;
        border-radius: 999px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #2a2a2a;
        color: #9f9f9f;
        font-size: 12px;
      }}

      .channel-name {{
        color: var(--muted);
        font-size: 12px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}

      .channel-name a {{
        color: inherit;
        text-decoration: none;
      }}

      .channel-name a:hover {{
        text-decoration: underline;
      }}

      @media (max-width: 2280px) {{
        .videos-grid {{
          grid-template-columns: repeat(4, 365px);
        }}
      }}

      @media (max-width: 1520px) {{
        .videos-grid {{
          grid-template-columns: repeat(3, 365px);
        }}
      }}

      @media (max-width: 1140px) {{
        .videos-grid,
        .shorts-grid {{
          grid-template-columns: repeat(2, 365px);
        }}
      }}

      @media (max-width: 760px) {{
        .videos-grid,
        .shorts-grid {{
          grid-template-columns: repeat(1, 365px);
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>For Us Page</h1>
      <p class="meta">Snapshot hash: <code>{escaped_hash}</code></p>
      <h2 class="section-title">Videos</h2>
      {videos}
      <h2 class="section-title">Shorts</h2>
      {shorts}
    </main>
  </body>
</html>
"""


def _render_video_grid(items: list[RecommendationItem], metadata_reference_time: datetime) -> str:
    if not items:
        return '<p class="empty">No videos.</p>'

    list_items: list[str] = []
    for item in items:
        escaped_hash = html.escape(item.video_hash)
        escaped_title = html.escape(item.title)
        href = f"https://www.youtube.com/watch?v={escaped_hash}"
        thumb = f"https://i.ytimg.com/vi/{escaped_hash}/hqdefault.jpg"
        list_items.append(
            (
                '<article class="video-card">'
                f'<a class="thumb" href="{href}" target="_blank" rel="noopener noreferrer">'
                f'<img src="{thumb}" alt="{escaped_title} thumbnail" loading="lazy">'
                '<span class="image-overlay" aria-hidden="true"></span>'
                '<span class="play-icon" aria-hidden="true">&#9658;</span>'
                "</a>"
                '<div class="card-body">'
                f'<h3 class="title">{escaped_title}</h3>'
                f"{_render_video_card_metadata(item, metadata_reference_time)}"
                "</div>"
                "</article>"
            )
        )
    return f'<section class="videos-grid">{"".join(list_items)}</section>'


def _render_shorts_grid(items: list[RecommendationItem], metadata_reference_time: datetime) -> str:
    if not items:
        return '<p class="empty">No shorts.</p>'

    list_items: list[str] = []
    for item in items:
        escaped_hash = html.escape(item.video_hash)
        escaped_title = html.escape(item.title)
        href = f"https://www.youtube.com/shorts/{escaped_hash}"
        thumb = f"https://i.ytimg.com/vi/{escaped_hash}/hqdefault.jpg"
        list_items.append(
            (
                '<article class="short-card">'
                f'<a class="thumb" href="{href}" target="_blank" rel="noopener noreferrer">'
                f'<img src="{thumb}" alt="{escaped_title} short thumbnail" loading="lazy">'
                "</a>"
                '<div class="card-body">'
                f'<h3 class="title">{escaped_title}</h3>'
                f"{_render_short_card_metadata(item, metadata_reference_time)}"
                "</div>"
                "</article>"
            )
        )
    return f'<section class="shorts-grid">{"".join(list_items)}</section>'


def _render_video_card_metadata(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    channel_html = _render_channel_line(item, include_fallback=True)
    stats_html = _render_stats_line(item, metadata_reference_time)
    return f"{channel_html}{stats_html}"


def _render_short_card_metadata(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    channel_html = _render_channel_line(item, include_fallback=False)
    stats_html = _render_stats_line(item, metadata_reference_time)
    return f"{channel_html}{stats_html}"


def _render_channel_line(item: RecommendationItem, *, include_fallback: bool) -> str:
    if item.channel_name is None and item.channel_link is None and item.channel_avatar is None:
        if not include_fallback:
            return ""
        name = "Unknown channel"
        avatar_html = '<span class="channel-avatar-placeholder" aria-hidden="true">?</span>'
        return (
            '<div class="channel">'
            f"{avatar_html}"
            f'<div class="channel-name">{html.escape(name)}</div>'
            "</div>"
        )

    name_source = item.channel_name or _channel_name_from_link(item.channel_link) or "Unknown channel"
    name = html.escape(name_source)
    name_html = name
    if item.channel_link is not None:
        escaped_link = html.escape(str(item.channel_link))
        name_html = f'<a href="{escaped_link}" target="_blank" rel="noopener noreferrer">{name}</a>'

    if item.channel_avatar is not None:
        escaped_avatar = html.escape(str(item.channel_avatar))
        avatar_html = f'<img class="channel-avatar" src="{escaped_avatar}" alt="{name} avatar" loading="lazy">'
    elif include_fallback:
        avatar_html = '<span class="channel-avatar-placeholder" aria-hidden="true">?</span>'
    else:
        return ""

    return (
        '<div class="channel">'
        f"{avatar_html}"
        f'<div class="channel-name">{name_html}</div>'
        "</div>"
    )


def _channel_name_from_link(channel_link: object) -> str | None:
    if channel_link is None:
        return None
    channel_link_text = str(channel_link).rstrip("/")
    if not channel_link_text:
        return None
    last_segment = channel_link_text.rsplit("/", maxsplit=1)[-1]
    if not last_segment:
        return None
    return last_segment


def _render_stats_line(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    parts: list[str] = []
    if item.view_count is not None:
        parts.append(html.escape(_format_compact_views(item.view_count)))
    if item.published_at is not None:
        parts.append(html.escape(_format_relative_time(item.published_at, metadata_reference_time)))
    if not parts:
        return ""
    return f'<div class="meta-line">{" • ".join(parts)}</div>'


def _resolve_metadata_reference_time(snapshot: StoredSnapshot) -> datetime:
    reference_time = snapshot.payload.captured_at or snapshot.created_at
    return _to_utc(reference_time)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_relative_time(published_at: datetime, reference_time: datetime) -> str:
    published = _to_utc(published_at)
    reference = _to_utc(reference_time)
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


def _format_compact_views(view_count: int) -> str:
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


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
