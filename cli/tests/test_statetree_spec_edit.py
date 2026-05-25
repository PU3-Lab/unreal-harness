"""Unit tests for spec-editing commands: add-state, add-task, add-transition,
add-condition, and the compile commandlet wrapper.
"""
import json
import pytest
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch

from ue_auto.commands.ai_statetree import (
    _cmd_statetree_add_state,
    _cmd_statetree_add_task,
    _cmd_statetree_add_transition,
    _cmd_statetree_add_condition,
    _cmd_statetree_compile,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _write_spec(path: Path, states: list | None = None) -> Path:
    """Write a minimal wire spec YAML and return the path."""
    data = {
        "statetree": {
            "asset": "/Game/AI/ST_EnemyAI",
            "states": states if states is not None else [],
        }
    }
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _read_spec(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class _AddStateArgs:
    def __init__(self, spec, name, result="result.json", parent=None):
        self.spec = spec
        self.name = name
        self.result = result
        self.parent = parent
        self.dry_run = False


class _AddTaskArgs:
    def __init__(self, spec, state, cls, result="result.json", params=None):
        self.spec = spec
        self.state = state
        self.cls = cls
        self.result = result
        self.params = params
        self.dry_run = False


class _AddTransitionArgs:
    def __init__(self, spec, state, trigger, target, result="result.json"):
        self.spec = spec
        self.state = state
        self.trigger = trigger
        self.target = target
        self.result = result
        self.dry_run = False


class _AddConditionArgs:
    def __init__(self, spec, state, transition_index, cls, result="result.json", params=None):
        self.spec = spec
        self.state = state
        self.transition_index = transition_index
        self.cls = cls
        self.result = result
        self.params = params
        self.dry_run = False


class _CompileArgs:
    def __init__(self, project=None, asset=None, result="result.json", out=None):
        self.project = project
        self.asset = asset
        self.result = result
        self.out = out
        self.dry_run = False


# ── add-state ─────────────────────────────────────────────────────────────────

def test_add_state_appends_new_state(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml")
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_state(
        _AddStateArgs(str(spec), "Idle", result=str(result_path))
    )

    assert ret == 0
    states = _read_spec(spec)["statetree"]["states"]
    assert any(s["name"] == "Idle" for s in states)


def test_add_state_writes_result_ok(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml")
    result_path = tmp_path / "result.json"

    _cmd_statetree_add_state(_AddStateArgs(str(spec), "Idle", result=str(result_path)))

    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_add_state_creates_states_key_if_absent(tmp_path):
    """Spec with no 'states' key at all still works."""
    raw = {"statetree": {"asset": "/Game/AI/ST"}}
    spec = tmp_path / "wire.yaml"
    spec.write_text(yaml.dump(raw), encoding="utf-8")
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_state(_AddStateArgs(str(spec), "Idle", result=str(result_path)))

    assert ret == 0
    assert any(s["name"] == "Idle" for s in _read_spec(spec)["statetree"]["states"])


def test_add_state_duplicate_name_returns_1(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Idle"}])
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_state(_AddStateArgs(str(spec), "Idle", result=str(result_path)))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "DUPLICATE_STATE"


def test_add_state_missing_spec_returns_1(tmp_path):
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_state(_AddStateArgs(None, "Idle", result=str(result_path)))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "MISSING_SPEC"


def test_add_state_missing_name_returns_1(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml")
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_state(_AddStateArgs(str(spec), None, result=str(result_path)))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "MISSING_NAME"


def test_add_state_spec_not_found_returns_1(tmp_path):
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_state(
        _AddStateArgs(str(tmp_path / "nonexistent.yaml"), "Idle", result=str(result_path))
    )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "SPEC_NOT_FOUND"


def test_add_state_dry_run_does_not_modify_spec(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml")
    result_path = tmp_path / "result.json"
    args = _AddStateArgs(str(spec), "Idle", result=str(result_path))
    args.dry_run = True

    ret = _cmd_statetree_add_state(args)

    assert ret == 0
    states = _read_spec(spec)["statetree"]["states"]
    assert len(states) == 0  # unchanged


# ── add-task ──────────────────────────────────────────────────────────────────

def test_add_task_appends_task_to_state(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Flee", "tasks": []}])
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_task(
        _AddTaskArgs(str(spec), "Flee", "FleeTask", result=str(result_path))
    )

    assert ret == 0
    states = _read_spec(spec)["statetree"]["states"]
    flee = next(s for s in states if s["name"] == "Flee")
    assert any(t["class"] == "FleeTask" for t in flee.get("tasks", []))


def test_add_task_with_params(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Flee"}])
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_task(
        _AddTaskArgs(
            str(spec), "Flee", "FleeTask",
            result=str(result_path),
            params='{"flee_distance": 800.0}',
        )
    )

    assert ret == 0
    states = _read_spec(spec)["statetree"]["states"]
    flee = next(s for s in states if s["name"] == "Flee")
    task = next(t for t in flee["tasks"] if t["class"] == "FleeTask")
    assert task.get("flee_distance") == pytest.approx(800.0)


def test_add_task_state_not_found_returns_1(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Idle"}])
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_task(
        _AddTaskArgs(str(spec), "Nonexistent", "FleeTask", result=str(result_path))
    )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "STATE_NOT_FOUND"


def test_add_task_missing_class_returns_1(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Flee"}])
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_task(
        _AddTaskArgs(str(spec), "Flee", None, result=str(result_path))
    )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "MISSING_CLASS"


def test_add_task_writes_result_ok(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Flee"}])
    result_path = tmp_path / "result.json"

    _cmd_statetree_add_task(
        _AddTaskArgs(str(spec), "Flee", "FleeTask", result=str(result_path))
    )

    data = json.loads(result_path.read_text())
    assert data["ok"] is True


# ── add-transition ────────────────────────────────────────────────────────────

def test_add_transition_appends_transition(tmp_path):
    spec = _write_spec(
        tmp_path / "wire.yaml",
        states=[{"name": "Idle"}, {"name": "Flee"}],
    )
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_transition(
        _AddTransitionArgs(str(spec), "Idle", "OnTick", "Flee", result=str(result_path))
    )

    assert ret == 0
    states = _read_spec(spec)["statetree"]["states"]
    idle = next(s for s in states if s["name"] == "Idle")
    assert any(
        t["trigger"] == "OnTick" and t["target"] == "Flee"
        for t in idle.get("transitions", [])
    )


def test_add_transition_state_not_found_returns_1(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Idle"}])
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_transition(
        _AddTransitionArgs(str(spec), "Ghost", "OnTick", "Idle", result=str(result_path))
    )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "STATE_NOT_FOUND"


def test_add_transition_writes_result_ok(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Idle"}, {"name": "Flee"}])
    result_path = tmp_path / "result.json"

    _cmd_statetree_add_transition(
        _AddTransitionArgs(str(spec), "Idle", "OnTick", "Flee", result=str(result_path))
    )

    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_add_transition_missing_state_arg_returns_1(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml")
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_transition(
        _AddTransitionArgs(str(spec), None, "OnTick", "Flee", result=str(result_path))
    )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "MISSING_STATE"


# ── add-condition ─────────────────────────────────────────────────────────────

def test_add_condition_appends_to_transition(tmp_path):
    states = [
        {
            "name": "Idle",
            "transitions": [{"trigger": "OnTick", "target": "Flee", "conditions": []}],
        }
    ]
    spec = _write_spec(tmp_path / "wire.yaml", states=states)
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_condition(
        _AddConditionArgs(str(spec), "Idle", 0, "IsPlayerNear", result=str(result_path))
    )

    assert ret == 0
    st = _read_spec(spec)["statetree"]["states"]
    idle = next(s for s in st if s["name"] == "Idle")
    conds = idle["transitions"][0]["conditions"]
    assert any(c["class"] == "IsPlayerNear" for c in conds)


def test_add_condition_with_params(tmp_path):
    states = [
        {"name": "Idle", "transitions": [{"trigger": "OnTick", "target": "Flee", "conditions": []}]}
    ]
    spec = _write_spec(tmp_path / "wire.yaml", states=states)
    result_path = tmp_path / "result.json"

    _cmd_statetree_add_condition(
        _AddConditionArgs(
            str(spec), "Idle", 0, "IsPlayerNear",
            result=str(result_path),
            params='{"radius": 500.0, "invert": false}',
        )
    )

    st = _read_spec(spec)["statetree"]["states"]
    cond = st[0]["transitions"][0]["conditions"][0]
    assert cond["radius"] == pytest.approx(500.0)
    assert cond["invert"] is False


def test_add_condition_state_not_found_returns_1(tmp_path):
    spec = _write_spec(tmp_path / "wire.yaml", states=[{"name": "Idle"}])
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_condition(
        _AddConditionArgs(str(spec), "Ghost", 0, "IsPlayerNear", result=str(result_path))
    )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "STATE_NOT_FOUND"


def test_add_condition_invalid_transition_index_returns_1(tmp_path):
    states = [{"name": "Idle", "transitions": [{"trigger": "OnTick", "target": "Flee"}]}]
    spec = _write_spec(tmp_path / "wire.yaml", states=states)
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_condition(
        _AddConditionArgs(str(spec), "Idle", 5, "IsPlayerNear", result=str(result_path))
    )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "TRANSITION_NOT_FOUND"


def test_add_condition_missing_class_returns_1(tmp_path):
    states = [{"name": "Idle", "transitions": [{"trigger": "OnTick", "target": "Flee"}]}]
    spec = _write_spec(tmp_path / "wire.yaml", states=states)
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_add_condition(
        _AddConditionArgs(str(spec), "Idle", 0, None, result=str(result_path))
    )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "MISSING_CLASS"


# ── compile ───────────────────────────────────────────────────────────────────

def test_compile_missing_project_returns_1(tmp_path):
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_compile(_CompileArgs(result=str(result_path)))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "MISSING_PROJECT"


def test_compile_missing_asset_returns_1(tmp_path):
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_compile(_CompileArgs(project="MyGame.uproject", result=str(result_path)))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "MISSING_ASSET"


def test_compile_editor_not_found_returns_1(tmp_path):
    result_path = tmp_path / "result.json"

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value=None):
        ret = _cmd_statetree_compile(
            _CompileArgs(project="MyGame.uproject", asset="/Game/AI/ST", result=str(result_path))
        )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "EDITOR_NOT_FOUND"


def test_compile_calls_commandlet_with_correct_args(tmp_path):
    result_path = tmp_path / "result.json"
    out_path = str(tmp_path / "statetree.compile.result.json")
    Path(out_path).write_text(json.dumps({"ok": True, "message": "Compiled"}), encoding="utf-8")

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.ai_statetree.subprocess.run", return_value=mock_proc) as mock_run:
        ret = _cmd_statetree_compile(
            _CompileArgs(
                project="MyGame.uproject",
                asset="/Game/AI/ST_EnemyAI",
                out=out_path,
                result=str(result_path),
            )
        )

    assert ret == 0
    cmd = mock_run.call_args[0][0]
    assert "-run=StateTreeCompileCommandlet" in cmd
    assert any("-asset=/Game/AI/ST_EnemyAI" in a for a in cmd)


def test_compile_success_writes_result_ok(tmp_path):
    result_path = tmp_path / "result.json"
    out_path = str(tmp_path / "statetree.compile.result.json")
    Path(out_path).write_text(json.dumps({"ok": True, "message": "Compiled"}), encoding="utf-8")

    mock_proc = MagicMock()
    mock_proc.returncode = 0

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.ai_statetree.subprocess.run", return_value=mock_proc):
        _cmd_statetree_compile(
            _CompileArgs(
                project="MyGame.uproject",
                asset="/Game/AI/ST_EnemyAI",
                out=out_path,
                result=str(result_path),
            )
        )

    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_compile_commandlet_failure_returns_1(tmp_path):
    result_path = tmp_path / "result.json"

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = "compile error"

    with patch("ue_auto.commands.ai_statetree.find_editor", return_value="/ue/UnrealEditor-Cmd"), \
         patch("ue_auto.commands.ai_statetree.subprocess.run", return_value=mock_proc):
        ret = _cmd_statetree_compile(
            _CompileArgs(
                project="MyGame.uproject",
                asset="/Game/AI/ST_EnemyAI",
                result=str(result_path),
            )
        )

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_compile_dry_run_skips_commandlet(tmp_path):
    result_path = tmp_path / "result.json"
    args = _CompileArgs(
        project="MyGame.uproject",
        asset="/Game/AI/ST_EnemyAI",
        result=str(result_path),
    )
    args.dry_run = True

    with patch("ue_auto.commands.ai_statetree.subprocess.run") as mock_run:
        ret = _cmd_statetree_compile(args)

    assert ret == 0
    mock_run.assert_not_called()
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert data.get("dry_run") is True
