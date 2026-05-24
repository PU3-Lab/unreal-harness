import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ue_auto.commands.asset import _cmd_asset_snapshot


class _Args:
    def __init__(self, **kwargs):
        self.project = kwargs.get("project", None)
        self.out = kwargs.get("out", None)
        self.result = kwargs.get("result", "result.json")
        self.dry_run = False
        self.apply = False


# ── missing project ────────────────────────────────────────────────────────────

def test_snapshot_missing_project_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(result=str(result_path))
    ret = _cmd_asset_snapshot(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "MISSING_PROJECT"


# ── editor not found ──────────────────────────────────────────────────────────

def test_snapshot_editor_not_found_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(project="MyGame.uproject", result=str(result_path))
    with patch("ue_auto.commands.asset.find_editor", return_value=None):
        ret = _cmd_asset_snapshot(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "EDITOR_NOT_FOUND"


# ── commandlet invocation ─────────────────────────────────────────────────────

def test_snapshot_calls_commandlet_with_correct_args(tmp_path):
    result_path = tmp_path / "result.json"
    out_path = str(tmp_path / "assets.snapshot.json")
    args = _Args(project="MyGame.uproject", out=out_path, result=str(result_path))

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("ue_auto.commands.asset.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.asset.subprocess.run", return_value=mock_proc) as mock_run:
        ret = _cmd_asset_snapshot(args)

    assert ret == 0
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[0] == "/ue/UnrealEditor-Cmd"
    assert "-run=AssetSnapshotCommandlet" in called_cmd
    assert any(a.startswith(f"-out={out_path}") for a in called_cmd)


def test_snapshot_default_out_path(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(project="MyGame.uproject", result=str(result_path))  # no --out

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("ue_auto.commands.asset.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.asset.subprocess.run", return_value=mock_proc) as mock_run:
        _cmd_asset_snapshot(args)

    called_cmd = mock_run.call_args[0][0]
    assert any("assets.snapshot.json" in a for a in called_cmd)


def test_snapshot_commandlet_failure_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(project="MyGame.uproject", result=str(result_path))

    mock_proc = MagicMock()
    mock_proc.returncode = 1

    with patch("ue_auto.commands.asset.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.asset.subprocess.run", return_value=mock_proc):
        ret = _cmd_asset_snapshot(args)

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "SNAPSHOT_FAILED"


def test_snapshot_success_writes_result_ok(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(project="MyGame.uproject", result=str(result_path))

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("ue_auto.commands.asset.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.asset.subprocess.run", return_value=mock_proc):
        ret = _cmd_asset_snapshot(args)

    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
