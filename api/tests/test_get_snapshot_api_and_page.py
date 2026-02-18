from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from for_us_api.app import create_app
from for_us_api.models import CreateSnapshotRequest, RecommendationItem
from for_us_api.store import SnapshotStore


def test_get_snapshot_api_returns_stored_payload(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "capturedAt": "2026-02-17T11:00:00Z",
        "pageUrl": "https://www.youtube.com/",
        "videos": [
            {
                "videoHash": "lzChIIJMpGk",
                "title": "deadlock: items for idiot",
                "channelName": "chalant",
                "channelLink": "https://www.youtube.com/@itschalant",
                "channelAvatar": "https://yt3.ggpht.com/avatar",
                "publishedAt": "2026-02-14T11:00:00Z",
                "viewCount": 81000,
            }
        ],
        "shorts": [
            {
                "videoHash": "dQw4w9WgXcQ",
                "title": "short sample",
                "viewCount": 32000,
            }
        ],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]

        get_response = client.get(f"/api/snapshots/{snapshot_hash}")

    assert get_response.status_code == 200
    assert get_response.json() == payload
    assert get_response.headers["etag"].startswith('"api-')
    assert "public, max-age=" in get_response.headers["cache-control"]
    assert "immutable" in get_response.headers["cache-control"]


def test_get_snapshot_api_returns_304_when_etag_matches(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "videos": [{"videoHash": "lzChIIJMpGk", "title": "example"}],
        "shorts": [],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]

        initial_get = client.get(f"/api/snapshots/{snapshot_hash}")
        etag = initial_get.headers["etag"]
        cached_get = client.get(
            f"/api/snapshots/{snapshot_hash}",
            headers={"If-None-Match": etag},
        )

    assert initial_get.status_code == 200
    assert cached_get.status_code == 304
    assert cached_get.headers["etag"] == etag


def test_render_snapshot_page_contains_video_and_short_links(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "capturedAt": "2026-02-17T11:00:00Z",
        "videos": [
            {
                "videoHash": "lzChIIJMpGk",
                "title": "deadlock: items for idiot",
                "channelName": "chalant",
                "channelLink": "https://www.youtube.com/@itschalant",
                "channelAvatar": "https://yt3.ggpht.com/avatar",
                "publishedAt": "2026-02-14T11:00:00Z",
                "viewCount": 81000,
            }
        ],
        "shorts": [{"videoHash": "dQw4w9WgXcQ", "title": "short sample", "viewCount": 32000}],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]

        page_response = client.get(f"/{snapshot_hash}")

    assert page_response.status_code == 200
    assert "myfyp (my for you page) by" in page_response.text
    assert 'href="https://dtsykunov.com/"' in page_response.text
    assert "Taken at: <code>2026-02-17 11:00:00 UTC</code>" in page_response.text
    assert "https://www.youtube.com/watch?v=lzChIIJMpGk" in page_response.text
    assert "https://www.youtube.com/shorts/dQw4w9WgXcQ" in page_response.text
    assert "deadlock: items for idiot" in page_response.text
    assert "chalant" in page_response.text
    assert "https://www.youtube.com/@itschalant" in page_response.text
    assert "https://yt3.ggpht.com/avatar" in page_response.text
    assert "81K views" in page_response.text
    assert "3 days ago" in page_response.text
    assert 'href="/"' in page_response.text
    assert 'href="/privacy"' in page_response.text
    assert page_response.headers["etag"].startswith('"html-')
    assert "public, max-age=" in page_response.headers["cache-control"]
    assert "immutable" in page_response.headers["cache-control"]


def test_render_snapshot_page_returns_304_when_etag_matches(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "videos": [{"videoHash": "lzChIIJMpGk", "title": "page cache"}],
        "shorts": [],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]
        initial_page = client.get(f"/{snapshot_hash}")
        etag = initial_page.headers["etag"]
        cached_page = client.get(
            f"/{snapshot_hash}",
            headers={"If-None-Match": etag},
        )

    assert initial_page.status_code == 200
    assert cached_page.status_code == 304
    assert cached_page.headers["etag"] == etag


def test_render_snapshot_page_with_missing_optional_metadata(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "videos": [
            {
                "videoHash": "lzChIIJMpGk",
                "title": "title without parsed date and views",
                "channelName": "fallback channel",
            }
        ],
        "shorts": [],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]
        page_response = client.get(f"/{snapshot_hash}")

    assert page_response.status_code == 200
    assert "title without parsed date and views" in page_response.text
    assert "fallback channel" in page_response.text


def test_render_snapshot_page_formats_large_views_and_relative_hours(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "capturedAt": "2026-02-17T11:00:00Z",
        "videos": [
            {
                "videoHash": "lzChIIJMpGk",
                "title": "formatting sample",
                "publishedAt": "2026-02-17T10:00:00Z",
                "viewCount": 1_500_000,
            }
        ],
        "shorts": [],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]
        page_response = client.get(f"/{snapshot_hash}")

    assert page_response.status_code == 200
    assert "1.5M views" in page_response.text
    assert "1 hour ago" in page_response.text


def test_get_snapshot_api_returns_404_for_unknown_hash(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        response = client.get("/api/snapshots/unknown123")

    assert response.status_code == 404


def test_root_page_includes_installation_instructions(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "myfyp (my for you page) by" in response.text
    assert "Install and Use" in response.text
    assert 'href="/"' in response.text
    assert 'href="http://testserver/myfyp.user.js"' in response.text
    assert 'href="/privacy"' in response.text


def test_userscript_endpoint_serves_userscript(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    database_path = tmp_path / "snapshots.db"
    userscript_path = tmp_path / "myfyp.user.js"
    userscript_text = "// ==UserScript==\n// @name Test\n// ==/UserScript=="
    userscript_path.write_text(userscript_text, encoding="utf-8")
    monkeypatch.setenv("FOR_US_USERSCRIPT_PATH", str(userscript_path))

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        response = client.get("/myfyp.user.js")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "no-cache"
    assert response.text == userscript_text


def test_privacy_page_is_available(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        response = client.get("/privacy")

    assert response.status_code == 200
    assert "Privacy Notice" in response.text
    assert 'href="/"' in response.text
    assert "Snapshots are automatically deleted after 7 days." in response.text
    assert 'href="/privacy"' in response.text


def test_expired_snapshot_is_cleaned_up_and_returns_404(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    store = SnapshotStore(database_path=database_path)
    store.initialize()
    expired_snapshot = store.create_snapshot(
        CreateSnapshotRequest(
            videos=[RecommendationItem(videoHash="lzChIIJMpGk", title="Sample video")], shorts=[]
        ),
        now=datetime.now(timezone.utc) - timedelta(days=8),
    )

    with TestClient(create_app(store=store)) as client:
        api_response = client.get(f"/api/snapshots/{expired_snapshot.hash}")
        page_response = client.get(f"/{expired_snapshot.hash}")

    assert api_response.status_code == 404
    assert page_response.status_code == 404


def test_remove_snapshot_endpoint_deletes_snapshot_when_token_matches(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "videos": [{"videoHash": "lzChIIJMpGk", "title": "remove me"}],
        "shorts": [],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        response_body = create_response.json()
        snapshot_hash = response_body["hash"]
        remove_token = response_body["removeToken"]

        remove_response = client.get(
            f"/api/snapshots/{snapshot_hash}/remove/{remove_token}"
        )
        get_response = client.get(f"/api/snapshots/{snapshot_hash}")

    assert remove_response.status_code == 200
    assert remove_response.json() == {"detail": "Snapshot removed."}
    assert get_response.status_code == 404


def test_remove_snapshot_endpoint_rejects_invalid_token(tmp_path: Path) -> None:
    database_path = tmp_path / "snapshots.db"
    payload = {
        "videos": [{"videoHash": "lzChIIJMpGk", "title": "keep me"}],
        "shorts": [],
    }

    with TestClient(create_app(store=SnapshotStore(database_path=database_path))) as client:
        create_response = client.post("/api/snapshots", json=payload)
        snapshot_hash = create_response.json()["hash"]

        remove_response = client.get(
            f"/api/snapshots/{snapshot_hash}/remove/{'B' * 32}"
        )
        get_response = client.get(f"/api/snapshots/{snapshot_hash}")

    assert remove_response.status_code == 403
    assert remove_response.json() == {"detail": "Invalid remove token."}
    assert get_response.status_code == 200
