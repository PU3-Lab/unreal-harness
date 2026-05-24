import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ue_auto.commands.test_cmd import _cmd_test_automation


class _Args:
    def __init__(self, **kw):
        self.project = kw.get("project", None)
        self.result = kw.get("result", "Saved/AutomationReports/result.json")
        self.filter = kw.get("filter", None)
        self.out = kw.get("out", None)
        self.timeout = kw.get("timeout", 300)


# ── _cmd_test_automation ───────────────────────────────────────────────────────

def test_cmd_test_automation_missing_project(tmp_path):
    result_path = tmp_path / "result.json"
    ret = _cmd_test_automation(_Args(project=None, result=str(result_path)))
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_test_automation_editor_not_found(tmp_path, monkeypatch):
    monkeypatch.delenv("UE_EDITOR_CMD", raising=False)
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.test_cmd.find_editor", return_value=None):
        ret = _cmd_test_automation(_Args(project="MyGame.uproject", result=str(result_path)))
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_test_automation_success(tmp_path, monkeypatch):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.test_cmd.find_editor", return_value="/fake/UnrealEditor-Cmd"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ret = _cmd_test_automation(_Args(project="MyGame.uproject", result=str(result_path)))
    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert data["action"] == "test"


def test_cmd_test_automation_failure(tmp_path):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.test_cmd.find_editor", return_value="/fake/UnrealEditor-Cmd"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            ret = _cmd_test_automation(_Args(project="MyGame.uproject", result=str(result_path)))
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_test_automation_subprocess_uses_automation_commandlet(tmp_path):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.test_cmd.find_editor", return_value="/fake/UnrealEditor-Cmd"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _cmd_test_automation(_Args(project="MyGame.uproject", result=str(result_path)))
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "/fake/UnrealEditor-Cmd"
    assert any("AutomationCommandlet" in arg or "Automation" in arg for arg in cmd)


def test_cmd_test_automation_with_filter(tmp_path):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.test_cmd.find_editor", return_value="/fake/UnrealEditor-Cmd"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _cmd_test_automation(_Args(
                project="MyGame.uproject",
                result=str(result_path),
                filter="MyGame.Tests",
            ))
    cmd = mock_run.call_args[0][0]
    assert any("MyGame.Tests" in arg for arg in cmd)


def test_cmd_test_automation_timeout_error(tmp_path):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.test_cmd.find_editor", return_value="/fake/UnrealEditor-Cmd"):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="ue", timeout=300)
            ret = _cmd_test_automation(_Args(project="MyGame.uproject", result=str(result_path)))
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
