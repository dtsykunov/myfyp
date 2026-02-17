from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import Response

from for_us_api.abuse import AbuseConfig, InMemoryAbuseGuard
from for_us_api.formatting import to_utc as _to_utc
from for_us_api.http_cache import (
    build_cache_headers as _build_cache_headers,
    build_etag as _build_etag,
    if_none_match_matches as _if_none_match_matches,
)
from for_us_api.models import CreateSnapshotRequest, CreateSnapshotResponse
from for_us_api.rendering import (
    render_home_html as _render_home_html,
    render_snapshot_html as _render_snapshot_html,
)
from for_us_api.store import DeleteSnapshotResult, SnapshotStore
from for_us_api.userscript import load_userscript_text as _load_userscript_text

DEFAULT_HTML_CACHE_ENTRIES = 2000


class _SnapshotHtmlCache:
    def __init__(self, max_entries: int = DEFAULT_HTML_CACHE_ENTRIES) -> None:
        if max_entries <= 0:
            raise ValueError("max_entries must be positive.")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, tuple[str, datetime]] = OrderedDict()
        self._lock = Lock()

    def get(self, snapshot_hash: str, now: datetime | None = None) -> str | None:
        effective_now = _to_utc(now or datetime.now(timezone.utc))
        with self._lock:
            entry = self._entries.get(snapshot_hash)
            if entry is None:
                return None
            html_document, expires_at = entry
            if _to_utc(expires_at) <= effective_now:
                self._entries.pop(snapshot_hash, None)
                return None
            self._entries.move_to_end(snapshot_hash)
            return html_document

    def set(
        self,
        snapshot_hash: str,
        html_document: str,
        expires_at: datetime,
        now: datetime | None = None,
    ) -> None:
        effective_now = _to_utc(now or datetime.now(timezone.utc))
        normalized_expires_at = _to_utc(expires_at)
        if normalized_expires_at <= effective_now:
            return
        with self._lock:
            self._entries[snapshot_hash] = (html_document, normalized_expires_at)
            self._entries.move_to_end(snapshot_hash)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)


def create_app(
    store: SnapshotStore | None = None,
    abuse_guard: InMemoryAbuseGuard | None = None,
) -> FastAPI:
    """Create and configure the API application."""
    snapshot_store = store or SnapshotStore.from_environment()
    guard = abuse_guard or InMemoryAbuseGuard(AbuseConfig())
    html_cache = _SnapshotHtmlCache()

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

    @app.get("/myfyp.user.js", name="get_userscript")
    def get_userscript() -> Response:  # pyright: ignore[reportUnusedFunction]
        try:
            userscript_text = _load_userscript_text()
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return Response(
            content=userscript_text,
            media_type="text/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/", response_class=HTMLResponse)
    def render_home_page(request: Request) -> HTMLResponse:  # pyright: ignore[reportUnusedFunction]
        userscript_url = str(request.url_for("get_userscript"))
        return HTMLResponse(_render_home_html(userscript_url), status_code=200)

    @app.post("/api/snapshots", status_code=201, response_model=CreateSnapshotResponse)
    def create_snapshot(request: Request, payload: CreateSnapshotRequest) -> CreateSnapshotResponse:  # pyright: ignore[reportUnusedFunction]
        allowed, reason = guard.allow_snapshot_create(_client_ip(request))
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)
        created = snapshot_store.create_snapshot(payload)
        snapshot_url = str(
            request.url_for(
                "render_snapshot_page",
                snapshot_hash=created.hash,
            )
        )
        remove_url = str(
            request.url_for(
                "remove_snapshot_by_token",
                snapshot_hash=created.hash,
                remove_token=created.remove_token,
            )
        )
        return created.model_copy(update={"url": snapshot_url, "remove_url": remove_url})

    @app.get(
        "/api/snapshots/{snapshot_hash}",
        response_model=CreateSnapshotRequest,
        response_model_exclude_none=True,
    )
    def get_snapshot(request: Request, snapshot_hash: str) -> Response | CreateSnapshotRequest:  # pyright: ignore[reportUnusedFunction]
        allowed, reason = guard.allow_snapshot_read(_client_ip(request))
        if not allowed:
            raise HTTPException(status_code=429, detail=reason)
        snapshot, is_expired = snapshot_store.get_snapshot(snapshot_hash)
        if is_expired:
            raise HTTPException(status_code=410, detail="Snapshot has expired.")
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Snapshot not found.")
        etag = _build_etag("api", snapshot.hash)
        cache_headers = _build_cache_headers(snapshot.expires_at, etag)
        if _if_none_match_matches(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=cache_headers)
        return JSONResponse(
            content=snapshot.payload.model_dump(by_alias=True, mode="json", exclude_none=True),
            headers=cache_headers,
        )

    @app.get("/{snapshot_hash}", response_class=HTMLResponse)
    def render_snapshot_page(request: Request, snapshot_hash: str) -> Response:  # pyright: ignore[reportUnusedFunction]
        allowed, _reason = guard.allow_snapshot_read(_client_ip(request))
        if not allowed:
            return HTMLResponse("<h1>429 Too Many Requests</h1>", status_code=429)
        snapshot, is_expired = snapshot_store.get_snapshot(snapshot_hash)
        if is_expired:
            return HTMLResponse("<h1>410 Snapshot expired</h1>", status_code=410)
        if snapshot is None:
            return HTMLResponse("<h1>404 Snapshot not found</h1>", status_code=404)
        etag = _build_etag("html", snapshot.hash)
        cache_headers = _build_cache_headers(snapshot.expires_at, etag)
        if _if_none_match_matches(request.headers.get("if-none-match"), etag):
            return Response(status_code=304, headers=cache_headers)

        cached_html = html_cache.get(snapshot.hash)
        if cached_html is None:
            cached_html = _render_snapshot_html(snapshot)
            html_cache.set(snapshot.hash, cached_html, snapshot.expires_at)
        return HTMLResponse(cached_html, status_code=200, headers=cache_headers)

    @app.get(
        "/api/snapshots/{snapshot_hash}/remove/{remove_token}",
        response_class=JSONResponse,
        name="remove_snapshot_by_token",
    )
    def remove_snapshot_by_token(snapshot_hash: str, remove_token: str) -> JSONResponse:  # pyright: ignore[reportUnusedFunction]
        result = snapshot_store.delete_snapshot(snapshot_hash=snapshot_hash, remove_token=remove_token)
        if result is DeleteSnapshotResult.NOT_FOUND:
            raise HTTPException(status_code=404, detail="Snapshot not found.")
        if result is DeleteSnapshotResult.INVALID_TOKEN:
            raise HTTPException(status_code=403, detail="Invalid remove token.")
        return JSONResponse({"detail": "Snapshot removed."}, status_code=200)

    return app


app = create_app()


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"
