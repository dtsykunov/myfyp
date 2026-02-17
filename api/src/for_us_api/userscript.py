from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_USERSCRIPT_PATH = Path("extension") / "userscript" / "myfyp.user.js"


def load_userscript_text() -> str:
    script_path = _resolve_userscript_path()

    try:
        return script_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem error path
        raise RuntimeError(f"Unable to load userscript from {script_path}.") from exc


def _resolve_userscript_path() -> Path:
    custom_path = os.environ.get("FOR_US_USERSCRIPT_PATH")
    if custom_path:
        return Path(custom_path).expanduser()

    current_file = Path(__file__).resolve()
    for base_path in current_file.parents:
        candidate = base_path / _DEFAULT_USERSCRIPT_PATH
        if candidate.exists():
            return candidate

    fallback = current_file.parents[2] / _DEFAULT_USERSCRIPT_PATH
    return fallback
