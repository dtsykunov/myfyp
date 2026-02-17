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
    escaped_taken_at = html.escape(_format_snapshot_taken_at(metadata_reference_time))
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>For You Page - {escaped_hash}</title>
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

      .top-header {{
        display: flex;
        align-items: center;
        gap: 12px;
        margin: 0 0 12px;
      }}

      .brand-logo {{
        width: 29px;
        height: 20px;
        flex-shrink: 0;
      }}

      .brand-logo svg {{
        width: 29px;
        height: 20px;
        display: block;
      }}

      h1 {{
        margin: 0;
        font-size: 28px;
      }}

      .meta {{
        margin: 0;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.4;
      }}

      .meta-stack {{
        margin: 0 0 24px;
        display: grid;
        gap: 2px;
      }}

      .section-title {{
        margin: 24px 0 12px;
        font-size: 22px;
      }}

      .shorts-section-title {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
      }}

      .shorts-icon {{
        width: 24px;
        height: 24px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }}

      .shorts-icon svg {{
        width: 24px;
        height: 24px;
        display: block;
      }}

      .videos-grid {{
        display: grid;
        grid-template-columns: repeat(6, 365px);
        gap: 16px;
        justify-content: center;
      }}

      .shorts-grid {{
        display: grid;
        grid-template-columns: repeat(6, 365px);
        gap: 16px;
        justify-content: center;
      }}

      .video-card {{
        width: 365px;
        min-height: 305px;
        background: var(--card);
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid transparent;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition:
          transform 250ms ease,
          box-shadow 250ms ease,
          border-color 250ms ease;
      }}

      .video-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.18);
        border-color: rgba(255, 255, 255, 0.12);
      }}

      .short-card {{
        width: 365px;
        min-height: 547px;
        background: var(--card);
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid transparent;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        transition:
          transform 250ms ease,
          box-shadow 250ms ease,
          border-color 250ms ease;
      }}

      .short-card:hover {{
        transform: translateY(-4px);
        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.18);
        border-color: rgba(255, 255, 255, 0.12);
      }}

      .thumb {{
        display: block;
      }}

      .video-card .thumb {{
        width: 365px;
        aspect-ratio: 16 / 9;
      }}

      .short-card .thumb {{
        width: 365px;
        aspect-ratio: 3 / 4;
      }}

      .video-card .thumb img {{
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }}

      .short-card .thumb img {{
        width: 100%;
        height: 100%;
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
        padding: 12px;
      }}

      .meta-line {{
        margin-top: 6px;
        color: var(--muted);
        font-size: 12px;
        line-height: 1.25;
      }}

      .card-meta {{
        display: flex;
        gap: 12px;
        align-items: flex-start;
      }}

      .meta-text {{
        display: flex;
        flex-direction: column;
        min-width: 0;
        flex: 1;
      }}

      .video-title {{
        margin: 0 0 6px;
        font-size: 14px;
        font-weight: 600;
        line-height: 1.3;
        color: var(--text);
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
      }}

      .channel-line {{
        color: var(--muted);
        font-size: 12px;
        line-height: 1.3;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }}

      .channel-row {{
        margin-top: 2px;
        color: var(--muted);
        font-size: 12px;
        line-height: 1.3;
      }}

      .channel-avatar {{
        width: 36px;
        height: 36px;
        border-radius: 999px;
        object-fit: cover;
        flex-shrink: 0;
      }}

      .channel-avatar-placeholder {{
        width: 36px;
        height: 36px;
        border-radius: 999px;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #2a2a2a;
        color: #9f9f9f;
        font-size: 14px;
      }}

      .channel-line a {{
        color: inherit;
        text-decoration: none;
      }}

      .channel-line a:hover {{
        text-decoration: underline;
      }}

      @media (max-width: 2280px) {{
        .videos-grid {{
          grid-template-columns: repeat(5, 365px);
        }}
        .shorts-grid {{
          grid-template-columns: repeat(5, 365px);
        }}
      }}

      @media (max-width: 1900px) {{
        .videos-grid {{
          grid-template-columns: repeat(4, 365px);
        }}
        .shorts-grid {{
          grid-template-columns: repeat(4, 365px);
        }}
      }}

      @media (max-width: 1520px) {{
        .videos-grid {{
          grid-template-columns: repeat(3, 365px);
        }}
        .shorts-grid {{
          grid-template-columns: repeat(3, 365px);
        }}
      }}

      @media (max-width: 1140px) {{
        .videos-grid {{
          grid-template-columns: repeat(2, 365px);
        }}
        .shorts-grid {{
          grid-template-columns: repeat(2, 365px);
        }}
      }}

      @media (max-width: 760px) {{
        .videos-grid {{
          grid-template-columns: repeat(1, minmax(0, 1fr));
        }}

        .shorts-grid {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 10px;
        }}

        .video-card {{
          width: 100%;
        }}

        .video-card .thumb {{
          width: 100%;
        }}

        .short-card {{
          width: 100%;
          min-height: 0;
        }}

        .short-card .thumb {{
          width: 100%;
        }}

        .short-card .card-body {{
          padding: 10px 8px;
        }}
      }}
    </style>
  </head>
  <body>
    <main>
      <header class="top-header">
        <span class="brand-logo" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" width="29" height="20" viewBox="0 0 29 20" focusable="false" aria-hidden="true">
            <path d="M14.4848 20C14.4848 20 23.5695 20 25.8229 19.4C27.0917 19.06 28.0459 18.08 28.3808 16.87C29 14.65 29 9.98 29 9.98C29 9.98 29 5.34 28.3808 3.14C28.0459 1.9 27.0917 0.94 25.8229 0.61C23.5695 0 14.4848 0 14.4848 0C14.4848 0 5.42037 0 3.17711 0.61C1.9286 0.94 0.954148 1.9 0.59888 3.14C0 5.34 0 9.98 0 9.98C0 9.98 0 14.65 0.59888 16.87C0.954148 18.08 1.9286 19.06 3.17711 19.4C5.42037 20 14.4848 20 14.4848 20Z" fill="#FF0033"></path>
            <path d="M19 10L11.5 5.75V14.25L19 10Z" fill="#fff"></path>
          </svg>
        </span>
        <h1>For You Page</h1>
      </header>
      <div class="meta-stack">
        <p class="meta">Taken at: <code>{escaped_taken_at}</code></p>
        <p class="meta">Snapshot hash: <code>{escaped_hash}</code></p>
      </div>
      <h2 class="section-title">Videos</h2>
      {videos}
      <h2 class="section-title shorts-section-title">
        <span class="shorts-icon" aria-hidden="true">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" focusable="false" aria-hidden="true">
            <path d="m19.45,3.88c1.12,1.82.48,4.15-1.42,5.22l-1.32.74.94.41c1.36.58,2.27,1.85,2.35,3.27.08,1.43-.68,2.77-1.97,3.49l-8,4.47c-1.91,1.06-4.35.46-5.48-1.35-1.12-1.82-.48-4.15,1.42-5.22l1.33-.74-.94-.41c-1.36-.58-2.27-1.85-2.35-3.27-.08-1.43.68-2.77,1.97-3.49l8-4.47c1.91-1.06,4.35-.46,5.48,1.35Z" fill="#f03"></path>
            <path d="m10,15l5-3-5-3v6Z" fill="#fff"></path>
          </svg>
        </span>
        <span>Shorts</span>
      </h2>
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
                "</a>"
                '<div class="card-body">'
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
    title_html = html.escape(item.title)
    avatar_html = _render_channel_avatar(item, include_fallback=True)
    channel_html = _render_channel_name(item, include_fallback=True)
    stats_text = _render_stats_text(item, metadata_reference_time)
    stats_html = f'<div class="channel-row">{html.escape(stats_text)}</div>' if stats_text else ""
    return (
        '<div class="card-meta">'
        f"{avatar_html}"
        '<div class="meta-text">'
        f'<h3 class="video-title">{title_html}</h3>'
        f'<div class="channel-line">{channel_html}</div>'
        f"{stats_html}"
        "</div>"
        "</div>"
    )


def _render_short_card_metadata(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    channel_html = _render_channel_name(item, include_fallback=False)
    stats_html = _render_stats_line(item, metadata_reference_time)
    if not channel_html:
        return stats_html
    return f'<div class="channel-line">{channel_html}</div>{stats_html}'


def _render_channel_name(item: RecommendationItem, *, include_fallback: bool) -> str:
    if item.channel_name is None and item.channel_link is None:
        if not include_fallback:
            return ""
        return html.escape("Unknown channel")
    name_source = item.channel_name or _channel_name_from_link(item.channel_link) or "Unknown channel"
    name = html.escape(name_source)
    name_html = name
    if item.channel_link is not None:
        escaped_link = html.escape(str(item.channel_link))
        name_html = f'<a href="{escaped_link}" target="_blank" rel="noopener noreferrer">{name}</a>'
    return name_html


def _render_channel_avatar(item: RecommendationItem, *, include_fallback: bool) -> str:
    if item.channel_avatar is not None:
        escaped_avatar = html.escape(str(item.channel_avatar))
        avatar_label = html.escape(item.channel_name or "Channel")
        return f'<img class="channel-avatar" src="{escaped_avatar}" alt="{avatar_label} avatar" loading="lazy">'
    if include_fallback:
        return '<span class="channel-avatar-placeholder" aria-hidden="true">?</span>'
    return ""


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
    stats_text = _render_stats_text(item, metadata_reference_time)
    if not stats_text:
        return ""
    return f'<div class="meta-line">{html.escape(stats_text)}</div>'


def _render_stats_text(item: RecommendationItem, metadata_reference_time: datetime) -> str:
    parts: list[str] = []
    if item.view_count is not None:
        parts.append(_format_compact_views(item.view_count))
    if item.published_at is not None:
        parts.append(_format_relative_time(item.published_at, metadata_reference_time))
    return " • ".join(parts)


def _resolve_metadata_reference_time(snapshot: StoredSnapshot) -> datetime:
    reference_time = snapshot.payload.captured_at or snapshot.created_at
    return _to_utc(reference_time)


def _format_snapshot_taken_at(taken_at: datetime) -> str:
    normalized = _to_utc(taken_at)
    return normalized.strftime("%Y-%m-%d %H:%M:%S UTC")


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
