import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from ue_auto.commands.ai_statetree import _cmd_statetree_wire, parse_wire_spec


class _Args:
    def __init__(self, **kwargs):
        self.project = kwargs.get("project", None)
        self.asset = kwargs.get("asset", None)
        self.out = kwargs.get("out", None)
        self.result = kwargs.get("result", "result.json")
        self.spec = kwargs.get("spec", None)
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


# ── parse_wire_spec ───────────────────────────────────────────────────────────

def test_parse_wire_spec_returns_dict(tmp_path):
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text(
        "statetree:\n  asset: /Game/AI/ST_EnemyAI\n  states: []\n",
        encoding="utf-8",
    )
    result = parse_wire_spec(str(spec_file))
    assert result["statetree"]["asset"] == "/Game/AI/ST_EnemyAI"


def test_parse_wire_spec_not_found_raises():
    with pytest.raises(FileNotFoundError, match="not found"):
        parse_wire_spec("/nonexistent/path/wire.spec.yaml")


def test_parse_wire_spec_missing_statetree_key_raises(tmp_path):
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text("other_key: value\n", encoding="utf-8")
    with pytest.raises(ValueError, match="statetree"):
        parse_wire_spec(str(spec_file))


def test_parse_wire_spec_missing_asset_key_raises(tmp_path):
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text("statetree:\n  states: []\n", encoding="utf-8")
    with pytest.raises(ValueError, match="asset"):
        parse_wire_spec(str(spec_file))


# ── spec-based wire ───────────────────────────────────────────────────────────

def test_wire_spec_not_found_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(
        project="MyGame.uproject",
        spec="/nonexistent/wire.spec.yaml",
        result=str(result_path),
    )
    ret = _cmd_statetree_wire(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "SPEC_NOT_FOUND"


def test_wire_spec_missing_asset_key_returns_1(tmp_path):
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text("statetree:\n  states: []\n", encoding="utf-8")
    result_path = tmp_path / "result.json"
    args = _Args(
        project="MyGame.uproject",
        spec=str(spec_file),
        result=str(result_path),
    )
    ret = _cmd_statetree_wire(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "SPEC_ERROR"


def test_wire_with_spec_uses_asset_from_spec(tmp_path):
    """No --asset given; spec provides the asset path."""
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text(
        "statetree:\n  asset: /Game/AI/ST_EnemyAI\n  states: []\n",
        encoding="utf-8",
    )
    out_path = str(tmp_path / "statetree.wire.result.json")
    Path(out_path).write_text(
        json.dumps({"ok": True, "message": "Wired"}), encoding="utf-8"
    )
    result_path = tmp_path / "result.json"
    args = _Args(
        project="MyGame.uproject",
        spec=str(spec_file),
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
    assert any("-asset=/Game/AI/ST_EnemyAI" in a for a in called_cmd)


def test_wire_with_spec_passes_spec_arg_to_commandlet(tmp_path):
    """When --spec is given, commandlet receives a -spec= argument."""
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text(
        "statetree:\n  asset: /Game/AI/ST_EnemyAI\n  states: []\n",
        encoding="utf-8",
    )
    out_path = str(tmp_path / "statetree.wire.result.json")
    Path(out_path).write_text(
        json.dumps({"ok": True, "message": "Wired"}), encoding="utf-8"
    )
    result_path = tmp_path / "result.json"
    args = _Args(
        project="MyGame.uproject",
        spec=str(spec_file),
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
    assert any(a.startswith("-spec=") for a in called_cmd)


def test_wire_dry_run_skips_commandlet(tmp_path):
    """dry_run=True returns 0 without calling subprocess.run."""
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text(
        "statetree:\n  asset: /Game/AI/ST_EnemyAI\n  states: []\n",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.json"
    args = _Args(
        project="MyGame.uproject",
        spec=str(spec_file),
        result=str(result_path),
    )
    args.dry_run = True

    with patch("ue_auto.commands.ai_statetree.subprocess.run") as mock_run:
        ret = _cmd_statetree_wire(args)

    assert ret == 0
    mock_run.assert_not_called()
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert data.get("dry_run") is True


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
