"""Runtime compatibility shim for pywrangler package resolution.

This project temporarily forces a newer Pyodide package index for pywrangler
because FastAPI/Pydantic versions used by myfyp are available in 0.29.3 while
workers-py currently resolves Python 3.13 to an older index.
"""

from __future__ import annotations

import os


def _apply_pywrangler_pyodide_index_patch() -> None:
    if os.environ.get("MYFYP_ENABLE_PYWRANGLER_PYODIDE_PATCH", "1") != "1":
        return

    try:
        import pywrangler.utils as pywrangler_utils
    except Exception:
        # Only patch when pywrangler is available in this Python process.
        return

    target_index = os.environ.get(
        "MYFYP_PYODIDE_INDEX", "https://index.pyodide.org/0.29.3"
    )

    def _patched_get_pyodide_index() -> str:
        return target_index

    pywrangler_utils.get_pyodide_index = _patched_get_pyodide_index


_apply_pywrangler_pyodide_index_patch()
