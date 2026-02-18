from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_WEB_ICONS_PATH = Path("brand") / "icons" / "web"
_SUPPORTED_ICON_FILES = {
    "favicon.ico",
    "favicon.svg",
    "favicon-16x16.png",
    "favicon-32x32.png",
    "favicon-48x48.png",
    "apple-touch-icon.png",
    "android-chrome-192x192.png",
    "android-chrome-512x512.png",
}


def load_web_icon_bytes(file_name: str) -> bytes:
    icon_path = _resolve_web_icon_path(file_name)

    try:
        return icon_path.read_bytes()
    except OSError as exc:  # pragma: no cover - filesystem error path
        raise RuntimeError(f"Unable to load web icon from {icon_path}.") from exc


def _resolve_web_icon_path(file_name: str) -> Path:
    if file_name not in _SUPPORTED_ICON_FILES:
        raise ValueError(f"Unsupported web icon file: {file_name}")

    custom_base = os.environ.get("FOR_US_WEB_ICONS_PATH")
    if custom_base:
        return Path(custom_base).expanduser() / file_name

    current_file = Path(__file__).resolve()
    for base_path in current_file.parents:
        candidate = base_path / _DEFAULT_WEB_ICONS_PATH / file_name
        if candidate.exists():
            return candidate

    fallback = current_file.parents[2] / _DEFAULT_WEB_ICONS_PATH / file_name
    return fallback
