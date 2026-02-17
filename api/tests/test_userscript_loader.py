# pyright: reportPrivateUsage=false

from pathlib import Path

from pytest import MonkeyPatch

from for_us_api import userscript


def test_resolve_userscript_path_prefers_env_override(monkeypatch: MonkeyPatch) -> None:
    custom_path = Path("/tmp/custom.user.js")
    monkeypatch.setenv("FOR_US_USERSCRIPT_PATH", str(custom_path))

    resolved = userscript._resolve_userscript_path()

    assert resolved == custom_path


def test_resolve_userscript_path_discovers_script_in_parent_tree(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    fake_file = tmp_path / "app" / "src" / "for_us_api" / "userscript.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.write_text("# stub", encoding="utf-8")

    userscript_file = tmp_path / "app" / "extension" / "userscript" / "myfyp.user.js"
    userscript_file.parent.mkdir(parents=True, exist_ok=True)
    userscript_file.write_text("// userscript", encoding="utf-8")

    monkeypatch.delenv("FOR_US_USERSCRIPT_PATH", raising=False)
    monkeypatch.setattr(userscript, "__file__", str(fake_file))

    resolved = userscript._resolve_userscript_path()

    assert resolved == userscript_file
