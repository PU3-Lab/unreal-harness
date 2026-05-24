import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ue_auto.commands.ai_statetree import _cmd_statetree_wire


class _Args:
    def __init__(self, **kwargs):
        self.project = kwargs.get("project", None)
        self.asset = kwargs.get("asset", None)
        self.out = kwargs.get("out", None)
        self.result = kwargs.get("result", "result.json")
        self.dry_run = False
        self.apply = False


# ── validation guards ─────────────────────────────────────────────────────────

def test_wire_missing_project_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(result=str(result_path))
    ret = _cmd_statetree_wire(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "MISSING_PROJECT"


def test_wire_missing_asset_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(project="MyGame.uproject", result=str(result_path))
    ret = _cmd_statetree_wire(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "MISSING_ASSET"


def test_wire_editor_not_found_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(project="MyGame.uproject", asset="/Game/AI/ST_EnemyAI", result=str(result_path))
    with patch("ue_auto.commands.ai_statetree.find_editor", return_value=None):
        ret = _cmd_statetree_wire(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "EDITOR_NOT_FOUND"


# ── commandlet invocation ─────────────────────────────────────────────────────

def test_wire_calls_commandlet_with_correct_args(tmp_path):
    result_path = tmp_path / "result.json"
    out_path = str(tmp_path / "statetree.wire.result.json")
    # Write a fake commandlet result so the command can read it back
    wire_result = {"ok": True, "message": "Wired and compiled: /Game/AI/ST_EnemyAI"}
    Path(out_path).write_text(json.dumps(wire_result), encoding="utf-8")

    args = _Args(
        project="MyGame.uproject",
        asset="/Game/AI/ST_EnemyAI",
        out=out_path,
        result=str(result_path),
    )

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.ai_statetree.subprocess.run", return_value=mock_proc) as mock_run:
        ret = _cmd_statetree_wire(args)

    assert ret == 0
    called_cmd = mock_run.call_args[0][0]
    assert called_cmd[0] == "/ue/UnrealEditor-Cmd"
    assert "-run=StateTreeWireCommandlet" in called_cmd
    assert any("-asset=/Game/AI/ST_EnemyAI" in a for a in called_cmd)
    assert any("statetree.wire.result.json" in a for a in called_cmd)


def test_wire_default_out_path(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(project="MyGame.uproject", asset="/Game/AI/ST_EnemyAI", result=str(result_path))

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.ai_statetree.subprocess.run", return_value=mock_proc) as mock_run:
        _cmd_statetree_wire(args)

    called_cmd = mock_run.call_args[0][0]
    assert any("statetree.wire.result.json" in a for a in called_cmd)


# ── commandlet failure cases ──────────────────────────────────────────────────

def test_wire_commandlet_nonzero_exit_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(project="MyGame.uproject", asset="/Game/AI/ST_EnemyAI", result=str(result_path))

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = ""

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.ai_statetree.subprocess.run", return_value=mock_proc):
        ret = _cmd_statetree_wire(args)

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_wire_commandlet_result_ok_false_returns_1(tmp_path):
    """Commandlet exits 0 but writes ok=false in result JSON."""
    out_path = tmp_path / "wire.result.json"
    result_path = tmp_path / "result.json"
    out_path.write_text(
        json.dumps({"ok": False, "error_code": "COMPILE_FAILED", "message": "compile error"}),
        encoding="utf-8",
    )
    args = _Args(
        project="MyGame.uproject",
        asset="/Game/AI/ST_EnemyAI",
        out=str(out_path),
        result=str(result_path),
    )

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = ""

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.ai_statetree.subprocess.run", return_value=mock_proc):
        ret = _cmd_statetree_wire(args)

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "COMPILE_FAILED"


# ── success path ──────────────────────────────────────────────────────────────

def test_wire_success_writes_result_ok(tmp_path):
    out_path = tmp_path / "wire.result.json"
    result_path = tmp_path / "result.json"
    out_path.write_text(
        json.dumps({"ok": True, "message": "Wired and compiled: /Game/AI/ST_EnemyAI"}),
        encoding="utf-8",
    )
    args = _Args(
        project="MyGame.uproject",
        asset="/Game/AI/ST_EnemyAI",
        out=str(out_path),
        result=str(result_path),
    )

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.ai_statetree.subprocess.run", return_value=mock_proc):
        ret = _cmd_statetree_wire(args)

    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
