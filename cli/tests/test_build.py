import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ue_auto.commands.build_cmd import (
    _build_platform,
    _editor_target,
    _cmd_build_editor,
    find_build_script,
)


# ── find_build_script ──────────────────────────────────────────────────────────

def test_find_build_script_uses_env_var(monkeypatch):
    monkeypatch.setenv("UE_BUILD_SCRIPT", "/custom/Build.sh")
    assert find_build_script() == "/custom/Build.sh"


def test_find_build_script_derives_from_editor_cmd(monkeypatch, tmp_path):
    monkeypatch.delenv("UE_BUILD_SCRIPT", raising=False)
    # Build.sh lives at Engine/Build/BatchFiles/ relative to the binary
    engine_dir = tmp_path / "Engine"
    batch_dir = engine_dir / "Build" / "BatchFiles"
    batch_dir.mkdir(parents=True)
    build_sh = batch_dir / "Build.sh"
    build_sh.touch()

    editor_cmd = str(engine_dir / "Binaries" / "Mac" / "UnrealEditor-Cmd")
    monkeypatch.setenv("UE_EDITOR_CMD", editor_cmd)
    monkeypatch.delenv("UE_BUILD_SCRIPT", raising=False)

    result = find_build_script()
    assert result == str(build_sh)


def test_find_build_script_returns_none_when_not_found(monkeypatch):
    monkeypatch.delenv("UE_BUILD_SCRIPT", raising=False)
    monkeypatch.delenv("UE_EDITOR_CMD", raising=False)
    assert find_build_script() is None


# ── _editor_target ─────────────────────────────────────────────────────────────

def test_editor_target_appends_editor():
    assert _editor_target("MyGame") == "MyGameEditor"


def test_editor_target_strips_uproject_suffix():
    assert _editor_target("/path/to/MyGame.uproject") == "MyGameEditor"


# ── _build_platform ────────────────────────────────────────────────────────────

def test_build_platform_mac():
    with patch("sys.platform", "darwin"):
        assert _build_platform() == "Mac"


def test_build_platform_windows():
    with patch("sys.platform", "win32"):
        assert _build_platform() == "Win64"


def test_build_platform_linux():
    with patch("sys.platform", "linux"):
        assert _build_platform() == "Linux"


# ── _cmd_build_editor ──────────────────────────────────────────────────────────

class _Args:
    def __init__(self, **kw):
        self.project = kw.get("project", None)
        self.result = kw.get("result", "Saved/AutomationReports/result.json")
        self.out = kw.get("out", None)
        self.config = kw.get("config", "Development")


def test_cmd_build_editor_missing_project(tmp_path):
    result_path = tmp_path / "result.json"
    ret = _cmd_build_editor(_Args(project=None, result=str(result_path)))
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_build_editor_build_script_not_found(tmp_path, monkeypatch):
    monkeypatch.delenv("UE_BUILD_SCRIPT", raising=False)
    monkeypatch.delenv("UE_EDITOR_CMD", raising=False)
    result_path = tmp_path / "result.json"
    ret = _cmd_build_editor(_Args(project="MyGame.uproject", result=str(result_path)))
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_build_editor_success(tmp_path, monkeypatch):
    monkeypatch.setenv("UE_BUILD_SCRIPT", "/fake/Build.sh")
    result_path = tmp_path / "result.json"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        ret = _cmd_build_editor(_Args(project="MyGame.uproject", result=str(result_path)))

    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert data["action"] == "build"


def test_cmd_build_editor_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("UE_BUILD_SCRIPT", "/fake/Build.sh")
    result_path = tmp_path / "result.json"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1)
        ret = _cmd_build_editor(_Args(project="MyGame.uproject", result=str(result_path)))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_build_editor_subprocess_called_with_correct_args(tmp_path, monkeypatch):
    monkeypatch.setenv("UE_BUILD_SCRIPT", "/fake/Build.sh")
    result_path = tmp_path / "result.json"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        _cmd_build_editor(_Args(project="MyGame.uproject", result=str(result_path)))

    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "/fake/Build.sh"
    assert "MyGameEditor" in cmd
