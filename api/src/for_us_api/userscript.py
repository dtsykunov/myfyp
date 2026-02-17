from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_USERSCRIPT_PATH = Path("extension") / "userscript" / "myfyp.user.js"


def load_userscript_text() -> str:
    custom_path = os.environ.get("FOR_US_USERSCRIPT_PATH")
    if custom_path:
        script_path = Path(custom_path).expanduser()
    else:
        repository_root = Path(__file__).resolve().parents[3]
        script_path = repository_root / _DEFAULT_USERSCRIPT_PATH

    try:
        return script_path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem error path
        raise RuntimeError(f"Unable to load userscript from {script_path}.") from exc
