from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import cast
from urllib.parse import urlparse

from pydantic import ValidationError as PydanticValidationError

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
from for_us_shared.rendering import render_home_html, render_snapshot_html

from for_us_worker.d1_abuse import allow_snapshot_create, allow_snapshot_read, cleanup_abuse_state
from for_us_worker.d1_store import create_snapshot, delete_expired_snapshots, get_snapshot_by_hash
from for_us_worker.types import RequestLike, WorkerEnv

_MAX_BODY_BYTES = 64 * 1024
_SNAPSHOT_HASH_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_ABUSE_CONFIG = AbuseConfig()
_USERSCRIPT_REDIRECT_URL = (
    "https://raw.githubusercontent.com/"
    "dtsykunov/myfyp/master/extension/userscript/myfyp.user.js"
)
_VALIDATION_ERRORS: tuple[type[Exception], ...] = (
    cast(type[Exception], PydanticValidationError),
    cast(type[Exception], PydanticV1ValidationError),
)


@dataclass(frozen=True)
class ResponseSpec:
    status: int
    body: str
    headers: dict[str, str]


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


async def handle_fetch(request: RequestLike, env: WorkerEnv) -> ResponseSpec:
    try:
        parsed_url = urlparse(request.url)
        path = parsed_url.path

        if request.method == "GET" and path == "/health":
            return json_response({"status": "ok"})

        if request.method == "GET" and path == "/":
            return html_response(render_home_html("https://myfyp.link/myfyp.user.js"))

        if request.method == "GET" and path == "/myfyp.user.js":
            return ResponseSpec(
                status=302,
                body="",
                headers={
                    "location": _USERSCRIPT_REDIRECT_URL,
                    "cache-control": "no-cache",
                },
            )

        if request.method == "POST" and path == "/api/snapshots":
            return await _handle_create_snapshot(request, env)

        if request.method == "GET" and path.startswith("/api/snapshots/"):
            snapshot_hash = path.removeprefix("/api/snapshots/")
            if not _SNAPSHOT_HASH_PATTERN.fullmatch(snapshot_hash):
                return json_response({"detail": "Snapshot not found."}, status=404)
            return await _handle_get_snapshot(request, env, snapshot_hash)

        if request.method == "GET" and _SNAPSHOT_HASH_PATTERN.fullmatch(path.removeprefix("/")):
            return await _handle_render_snapshot(path.removeprefix("/"), request, env)

        return json_response({"detail": "Not found."}, status=404)
    except _VALIDATION_ERRORS as exc:
        return json_response({"detail": _extract_validation_errors(exc)}, status=422)
    except ValueError as exc:
        return json_response({"detail": str(exc)}, status=400)
    except Exception:
        return json_response({"detail": "Internal server error."}, status=500)


async def handle_scheduled(env: WorkerEnv) -> None:
    await delete_expired_snapshots(env)
    await cleanup_abuse_state(env)


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

    response_payload = model_to_json_dict(
        CreateSnapshotResponse(
            hash=stored_snapshot.hash,
            expiresAt=stored_snapshot.expires_at,
        ),
        by_alias=True,
    )
    return json_response(response_payload, status=201)


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
