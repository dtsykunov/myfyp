# pyright: reportUnusedFunction=false

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Awaitable, Callable, cast
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response as StarletteResponse

try:
    from pydantic.v1 import ValidationError as PydanticV1ValidationError
except ImportError:  # pragma: no cover - pydantic v1 runtime
    PydanticV1ValidationError = PydanticValidationError

from for_us_shared.abuse import AbuseConfig
from for_us_shared.http_cache import build_cache_headers, build_etag, if_none_match_matches
from for_us_shared.models import (
    CreateSnapshotResponse,
    model_to_json_dict,
    parse_create_snapshot_request_json,
)
from for_us_shared.rendering import render_home_html, render_privacy_html, render_snapshot_html

from for_us_worker.d1_abuse import allow_snapshot_create, allow_snapshot_read, cleanup_abuse_state
from for_us_worker.d1_store import (
    DeleteSnapshotResult,
    create_snapshot,
    delete_expired_snapshots,
    delete_snapshot_by_hash_and_token,
    get_snapshot_by_hash,
)
from for_us_worker.types import RequestLike, WorkerEnv

_MAX_BODY_BYTES = 64 * 1024
_SNAPSHOT_HASH_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_REMOVE_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_ABUSE_CONFIG = AbuseConfig()
_USERSCRIPT_REDIRECT_URL = (
    "https://raw.githubusercontent.com/"
    "dtsykunov/myfyp/master/extension/userscript/myfyp.user.js"
)
_ICON_REDIRECT_BASE_URL = (
    "https://media.githubusercontent.com/media/"
    "dtsykunov/myfyp/refs/heads/master/brand/icons/web"
)
_ICON_FILE_NAMES = {
    "favicon.ico",
    "favicon.svg",
    "favicon-16x16.png",
    "favicon-32x32.png",
    "favicon-48x48.png",
    "apple-touch-icon.png",
    "android-chrome-192x192.png",
    "android-chrome-512x512.png",
}
_VALIDATION_ERRORS: tuple[type[Exception], ...] = (
    cast(type[Exception], PydanticValidationError),
    cast(type[Exception], PydanticV1ValidationError),
)


@dataclass(frozen=True)
class ResponseSpec:
    status: int
    body: str
    headers: dict[str, str]


class _RequestHeadersAdapter:
    def __init__(self, headers: Headers) -> None:
        self._headers = headers

    def get(self, name: str) -> str | None:
        return self._headers.get(name)


class _FastAPIRequestAdapter:
    def __init__(self, request: Request) -> None:
        self._request = request
        self._headers = _RequestHeadersAdapter(request.headers)

    @property
    def method(self) -> str:
        return self._request.method

    @property
    def url(self) -> str:
        return str(self._request.url)

    @property
    def headers(self) -> _RequestHeadersAdapter:
        return self._headers

    async def text(self) -> str:
        body = await self._request.body()
        return body.decode("utf-8")


def _adapt_fastapi_request(request: Request) -> RequestLike:
    return _FastAPIRequestAdapter(request)


def json_response(
    payload: object,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> ResponseSpec:
    resolved_headers = dict(headers or {})
    resolved_headers.setdefault("content-type", "application/json; charset=utf-8")
    return ResponseSpec(status=status, body=json.dumps(payload), headers=resolved_headers)


def html_response(
    payload: str,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> ResponseSpec:
    resolved_headers = dict(headers or {})
    resolved_headers.setdefault("content-type", "text/html; charset=utf-8")
    return ResponseSpec(status=status, body=payload, headers=resolved_headers)


def _to_starlette_response(response: ResponseSpec) -> StarletteResponse:
    return StarletteResponse(content=response.body, status_code=response.status, headers=response.headers)


async def _execute_with_error_handling(handler: Callable[[], Awaitable[ResponseSpec]]) -> ResponseSpec:
    try:
        return await handler()
    except _VALIDATION_ERRORS as exc:
        return json_response({"detail": _extract_validation_errors(exc)}, status=422)
    except ValueError as exc:
        return json_response({"detail": str(exc)}, status=400)
    except Exception as exc:
        return json_response({"detail": f"Internal server error: {exc}"}, status=500)


def _env_from_request(request: Request) -> WorkerEnv:
    env = request.scope.get("env")
    if env is None:
        raise RuntimeError("Worker environment is unavailable.")
    return cast(WorkerEnv, env)


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def _inject_fallback_env(
    request: Request,
    call_next: Callable[[Request], Awaitable[StarletteResponse]],
) -> StarletteResponse:
    if "env" not in request.scope:
        fallback_env = cast(WorkerEnv | None, getattr(app.state, "env", None))
        if fallback_env is not None:
            request.scope["env"] = fallback_env
    return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    del request
    if exc.status_code == 404:
        return JSONResponse({"detail": "Not found."}, status_code=404)

    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/health")
async def health_route() -> StarletteResponse:
    return _to_starlette_response(json_response({"status": "ok"}))


@app.get("/")
async def root_route(request: Request) -> StarletteResponse:
    adapted_request = _adapt_fastapi_request(request)
    response_spec = await _execute_with_error_handling(
        lambda: _handle_root(adapted_request)
    )
    return _to_starlette_response(response_spec)


@app.get("/privacy")
async def privacy_route() -> StarletteResponse:
    return _to_starlette_response(html_response(render_privacy_html()))


@app.post("/api/snapshots")
async def create_snapshot_route(request: Request) -> StarletteResponse:
    response_spec = await _execute_with_error_handling(
        lambda: _handle_create_snapshot(_adapt_fastapi_request(request), _env_from_request(request))
    )
    return _to_starlette_response(response_spec)


@app.get("/api/snapshots/{snapshot_hash}/remove/{remove_token}")
async def remove_snapshot_route(snapshot_hash: str, remove_token: str, request: Request) -> StarletteResponse:
    response_spec = await _execute_with_error_handling(
        lambda: _handle_remove_snapshot(_env_from_request(request), snapshot_hash, remove_token)
    )
    return _to_starlette_response(response_spec)


@app.get("/api/snapshots/{snapshot_hash}")
async def get_snapshot_route(snapshot_hash: str, request: Request) -> StarletteResponse:
    response_spec = await _execute_with_error_handling(
        lambda: _handle_get_snapshot_route(_adapt_fastapi_request(request), _env_from_request(request), snapshot_hash)
    )
    return _to_starlette_response(response_spec)


@app.get("/{candidate}")
async def candidate_route(candidate: str, request: Request) -> StarletteResponse:
    response_spec = await _execute_with_error_handling(
        lambda: _handle_candidate_route(candidate, _adapt_fastapi_request(request), _env_from_request(request))
    )
    return _to_starlette_response(response_spec)


async def handle_fetch(request: RequestLike, env: WorkerEnv) -> ResponseSpec:
    return await _execute_with_error_handling(lambda: _dispatch_request(request, env))


async def _dispatch_request(request: RequestLike, env: WorkerEnv) -> ResponseSpec:
    parsed_url = urlparse(request.url)
    path = parsed_url.path

    if request.method == "GET" and path == "/health":
        return json_response({"status": "ok"})

    if request.method == "GET" and path == "/":
        return await _handle_root(request)

    if request.method == "GET" and path == "/privacy":
        return html_response(render_privacy_html())

    if request.method == "POST" and path == "/api/snapshots":
        return await _handle_create_snapshot(request, env)

    remove_match = re.fullmatch(r"/api/snapshots/([A-Za-z0-9_-]{8,64})/remove/([A-Za-z0-9_-]{16,128})", path)
    if request.method == "GET" and remove_match:
        return await _handle_remove_snapshot(env, remove_match.group(1), remove_match.group(2))

    if request.method == "GET" and path.startswith("/api/snapshots/"):
        snapshot_hash = path.removeprefix("/api/snapshots/")
        return await _handle_get_snapshot_route(request, env, snapshot_hash)

    if request.method == "GET" and path.startswith("/") and "/" not in path.removeprefix("/"):
        return await _handle_candidate_route(path.removeprefix("/"), request, env)

    return json_response({"detail": "Not found."}, status=404)


async def handle_scheduled(env: WorkerEnv) -> None:
    await delete_expired_snapshots(env)
    await cleanup_abuse_state(env)


async def _handle_root(request: RequestLike) -> ResponseSpec:
    return html_response(
        render_home_html(
            userscript_url=_USERSCRIPT_REDIRECT_URL,
            site_url=f"{_base_url(request)}/",
        )
    )


async def _handle_get_snapshot_route(request: RequestLike, env: WorkerEnv, snapshot_hash: str) -> ResponseSpec:
    if not _SNAPSHOT_HASH_PATTERN.fullmatch(snapshot_hash):
        return json_response({"detail": "Snapshot not found."}, status=404)
    return await _handle_get_snapshot(request, env, snapshot_hash)


async def _handle_candidate_route(candidate: str, request: RequestLike, env: WorkerEnv) -> ResponseSpec:
    if candidate in _ICON_FILE_NAMES:
        return ResponseSpec(
            status=302,
            body="",
            headers={
                "location": f"{_ICON_REDIRECT_BASE_URL}/{candidate}",
                "cache-control": "public, max-age=86400, immutable",
            },
        )

    if _SNAPSHOT_HASH_PATTERN.fullmatch(candidate):
        return await _handle_render_snapshot(candidate, request, env)

    return json_response({"detail": "Not found."}, status=404)


async def _handle_create_snapshot(request: RequestLike, env: WorkerEnv) -> ResponseSpec:
    if _is_abuse_limiting_enabled(env):
        create_decision = await allow_snapshot_create(
            env=env,
            client_ip=_client_ip(request),
            config=_ABUSE_CONFIG,
        )
        if not create_decision.allowed:
            return json_response({"detail": create_decision.reason}, status=429)

    body_text = await _read_body_with_limit(request, _MAX_BODY_BYTES)
    payload = parse_create_snapshot_request_json(body_text)
    stored_snapshot = await create_snapshot(env, payload)
    base_url = _base_url(request)
    snapshot_url = f"{base_url}/{stored_snapshot.hash}"
    remove_url = f"{base_url}/api/snapshots/{stored_snapshot.hash}/remove/{stored_snapshot.delete_token}"

    response_payload = model_to_json_dict(
        CreateSnapshotResponse(
            hash=stored_snapshot.hash,
            expiresAt=stored_snapshot.expires_at,
            removeToken=stored_snapshot.delete_token,
            url=snapshot_url,
            removeUrl=remove_url,
        ),
        by_alias=True,
    )
    return json_response(response_payload, status=201)


async def _handle_remove_snapshot(
    env: WorkerEnv,
    snapshot_hash: str,
    remove_token: str,
) -> ResponseSpec:
    if not _SNAPSHOT_HASH_PATTERN.fullmatch(snapshot_hash):
        return json_response({"detail": "Snapshot not found."}, status=404)
    if not _REMOVE_TOKEN_PATTERN.fullmatch(remove_token):
        return json_response({"detail": "Invalid remove token."}, status=403)

    result = await delete_snapshot_by_hash_and_token(
        env=env,
        snapshot_hash=snapshot_hash,
        remove_token=remove_token,
    )
    if result is DeleteSnapshotResult.NOT_FOUND:
        return json_response({"detail": "Snapshot not found."}, status=404)
    if result is DeleteSnapshotResult.INVALID_TOKEN:
        return json_response({"detail": "Invalid remove token."}, status=403)
    return json_response({"detail": "Snapshot removed."}, status=200)


async def _handle_get_snapshot(request: RequestLike, env: WorkerEnv, snapshot_hash: str) -> ResponseSpec:
    if _is_abuse_limiting_enabled(env):
        read_decision = await allow_snapshot_read(
            env=env,
            client_ip=_client_ip(request),
            config=_ABUSE_CONFIG,
        )
        if not read_decision.allowed:
            return json_response({"detail": read_decision.reason}, status=429)

    lookup = await get_snapshot_by_hash(env, snapshot_hash)
    if lookup.is_expired:
        return json_response({"detail": "Snapshot has expired."}, status=410)
    if lookup.snapshot is None:
        return json_response({"detail": "Snapshot not found."}, status=404)

    etag = build_etag("api", lookup.snapshot.hash)
    cache_headers = build_cache_headers(lookup.snapshot.expires_at, etag)
    if if_none_match_matches(request.headers.get("if-none-match"), etag):
        return ResponseSpec(status=304, body="", headers=cache_headers)

    return json_response(
        model_to_json_dict(lookup.snapshot.payload, by_alias=True, exclude_none=True),
        headers=cache_headers,
    )


async def _handle_render_snapshot(snapshot_hash: str, request: RequestLike, env: WorkerEnv) -> ResponseSpec:
    if _is_abuse_limiting_enabled(env):
        read_decision = await allow_snapshot_read(
            env=env,
            client_ip=_client_ip(request),
            config=_ABUSE_CONFIG,
        )
        if not read_decision.allowed:
            return html_response("<h1>429 Too Many Requests</h1>", status=429)

    lookup = await get_snapshot_by_hash(env, snapshot_hash)
    if lookup.is_expired:
        return html_response("<h1>410 Snapshot expired</h1>", status=410)
    if lookup.snapshot is None:
        return html_response("<h1>404 Snapshot not found</h1>", status=404)

    etag = build_etag("html", lookup.snapshot.hash)
    cache_headers = build_cache_headers(lookup.snapshot.expires_at, etag)
    if if_none_match_matches(request.headers.get("if-none-match"), etag):
        return ResponseSpec(status=304, body="", headers=cache_headers)

    return html_response(render_snapshot_html(lookup.snapshot), headers=cache_headers)


async def _read_body_with_limit(request: RequestLike, max_bytes: int) -> str:
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            parsed_length = int(content_length)
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header.") from exc
        if parsed_length > max_bytes:
            raise ValueError("Request body too large.")

    body_text = await request.text()
    if len(body_text.encode("utf-8")) > max_bytes:
        raise ValueError("Request body too large.")
    return body_text


def _client_ip(request: RequestLike) -> str:
    cf_connecting_ip = request.headers.get("cf-connecting-ip")
    if cf_connecting_ip:
        return cf_connecting_ip.strip()

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return "unknown"


def _extract_validation_errors(exc: Exception) -> list[object]:
    errors_getter = getattr(exc, "errors", None)
    if callable(errors_getter):
        errors = errors_getter()
        if isinstance(errors, list):
            return cast(list[object], errors)
    return [str(exc)]


def _is_abuse_limiting_enabled(env: WorkerEnv) -> bool:
    raw_value = getattr(env, "ABUSE_LIMITING_ENABLED", "1")
    normalized = str(raw_value).strip().lower()
    return normalized not in {"0", "false", "no", "off"}


def _base_url(request: RequestLike) -> str:
    parsed = urlparse(request.url)
    return f"{parsed.scheme}://{parsed.netloc}"
