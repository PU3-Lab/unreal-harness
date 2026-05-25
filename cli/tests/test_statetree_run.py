"""Tests for ue-auto ai statetree run (TDD — RED first)."""
import copy
import json
import textwrap
import pytest
from pathlib import Path

from ue_auto.commands.ai_statetree import (
    parse_run_spec,
    apply_run_step,
    run_spec,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

_INITIAL_STATE = {
    "states": [
        {"name": "Root", "tasks": [], "transitions": [], "conditions": []}
    ]
}


def _with_state(spec: dict, name: str, parent: str = "Root") -> dict:
    return apply_run_step(spec, "add_state", {"name": name, "parent": parent})


# ── parse_run_spec ────────────────────────────────────────────────────────────

def test_parse_run_spec_returns_steps_list(tmp_path):
    f = tmp_path / "spec.yaml"
    f.write_text("steps:\n  - add_state: {name: Idle, parent: Root}\n")
    result = parse_run_spec(str(f))
    assert "steps" in result
    assert len(result["steps"]) == 1


def test_parse_run_spec_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_run_spec(str(tmp_path / "missing.yaml"))


def test_parse_run_spec_missing_steps_raises(tmp_path):
    f = tmp_path / "spec.yaml"
    f.write_text("asset: /Game/AI/ST_Test\n")
    with pytest.raises(ValueError, match="steps"):
        parse_run_spec(str(f))


def test_parse_run_spec_steps_must_be_list(tmp_path):
    f = tmp_path / "spec.yaml"
    f.write_text("steps: not_a_list\n")
    with pytest.raises(ValueError, match="steps"):
        parse_run_spec(str(f))


def test_parse_run_spec_optional_asset_field(tmp_path):
    f = tmp_path / "spec.yaml"
    f.write_text(
        "asset: /Game/AI/ST_Test\nsteps:\n  - add_state: {name: Idle, parent: Root}\n"
    )
    result = parse_run_spec(str(f))
    assert result.get("asset") == "/Game/AI/ST_Test"


def test_parse_run_spec_empty_steps_is_valid(tmp_path):
    f = tmp_path / "spec.yaml"
    f.write_text("steps: []\n")
    result = parse_run_spec(str(f))
    assert result["steps"] == []


# ── apply_run_step ────────────────────────────────────────────────────────────

def test_apply_run_step_add_state_to_root():
    new_spec = apply_run_step(_INITIAL_STATE, "add_state", {"name": "Idle", "parent": "Root"})
    names = [s["name"] for s in new_spec["states"]]
    assert "Idle" in names


def test_apply_run_step_does_not_mutate_original():
    original = copy.deepcopy(_INITIAL_STATE)
    apply_run_step(_INITIAL_STATE, "add_state", {"name": "Idle", "parent": "Root"})
    assert _INITIAL_STATE == original


def test_apply_run_step_add_state_missing_parent_raises():
    with pytest.raises(ValueError, match="parent"):
        apply_run_step(_INITIAL_STATE, "add_state", {"name": "Idle", "parent": "NonExistent"})


def test_apply_run_step_add_state_duplicate_name_raises():
    spec = _with_state(_INITIAL_STATE, "Idle")
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        apply_run_step(spec, "add_state", {"name": "Idle", "parent": "Root"})


def test_apply_run_step_add_task_to_state():
    spec = _with_state(_INITIAL_STATE, "Idle")
    spec = apply_run_step(spec, "add_task", {"state": "Idle", "task": "STT_Wait", "params": {}})
    idle = next(s for s in spec["states"] if s["name"] == "Idle")
    assert any(t["task"] == "STT_Wait" for t in idle["tasks"])


def test_apply_run_step_add_task_preserves_params():
    spec = _with_state(_INITIAL_STATE, "Idle")
    spec = apply_run_step(spec, "add_task", {"state": "Idle", "task": "STT_Wait", "params": {"Duration": 2.0}})
    idle = next(s for s in spec["states"] if s["name"] == "Idle")
    task = next(t for t in idle["tasks"] if t["task"] == "STT_Wait")
    assert task["params"]["Duration"] == 2.0


def test_apply_run_step_add_task_missing_state_raises():
    with pytest.raises(ValueError, match="[Ss]tate"):
        apply_run_step(_INITIAL_STATE, "add_task", {"state": "NonExistent", "task": "STT_Wait", "params": {}})


def test_apply_run_step_add_transition_between_states():
    spec = _with_state(_INITIAL_STATE, "Idle")
    spec = _with_state(spec, "Patrol")
    spec = apply_run_step(spec, "add_transition", {"from": "Idle", "to": "Patrol"})
    idle = next(s for s in spec["states"] if s["name"] == "Idle")
    assert any(t["to"] == "Patrol" for t in idle["transitions"])


def test_apply_run_step_add_transition_missing_from_raises():
    spec = _with_state(_INITIAL_STATE, "Patrol")
    with pytest.raises(ValueError, match="[Ff]rom|[Ss]tate"):
        apply_run_step(spec, "add_transition", {"from": "NonExistent", "to": "Patrol"})


def test_apply_run_step_add_transition_missing_to_raises():
    spec = _with_state(_INITIAL_STATE, "Idle")
    with pytest.raises(ValueError, match="[Tt]o|[Ss]tate"):
        apply_run_step(spec, "add_transition", {"from": "Idle", "to": "NonExistent"})


def test_apply_run_step_add_condition_to_transition():
    spec = _with_state(_INITIAL_STATE, "Idle")
    spec = _with_state(spec, "Patrol")
    spec = apply_run_step(spec, "add_transition", {"from": "Idle", "to": "Patrol"})
    spec = apply_run_step(spec, "add_condition", {"from": "Idle", "to": "Patrol", "condition": "HasTarget"})
    idle = next(s for s in spec["states"] if s["name"] == "Idle")
    tr = next(t for t in idle["transitions"] if t["to"] == "Patrol")
    assert "HasTarget" in tr.get("conditions", [])


def test_apply_run_step_unknown_type_raises():
    with pytest.raises(ValueError, match="[Uu]nknown"):
        apply_run_step(_INITIAL_STATE, "unknown_step", {})


# ── run_spec ──────────────────────────────────────────────────────────────────

def test_run_spec_executes_steps_in_order():
    steps = [
        {"add_state": {"name": "Idle", "parent": "Root"}},
        {"add_state": {"name": "Patrol", "parent": "Root"}},
        {"add_transition": {"from": "Idle", "to": "Patrol"}},
    ]
    result = run_spec(steps)
    assert result["ok"] is True
    assert result["steps_completed"] == 3


def test_run_spec_stops_on_first_failure():
    steps = [
        {"add_state": {"name": "Idle", "parent": "Root"}},
        {"add_state": {"name": "Idle", "parent": "Root"}},  # duplicate → fail
        {"add_state": {"name": "Patrol", "parent": "Root"}},  # should not execute
    ]
    result = run_spec(steps)
    assert result["ok"] is False
    assert result["steps_completed"] == 1


def test_run_spec_returns_per_step_results():
    steps = [{"add_state": {"name": "Idle", "parent": "Root"}}]
    result = run_spec(steps)
    assert "results" in result
    assert len(result["results"]) == 1
    assert result["results"][0]["ok"] is True


def test_run_spec_failed_step_has_error_message():
    steps = [{"add_state": {"name": "Idle", "parent": "Missing"}}]
    result = run_spec(steps)
    assert result["ok"] is False
    assert result["results"][0]["ok"] is False
    assert result["results"][0].get("error")


def test_run_spec_dry_run_returns_results_without_error():
    steps = [{"add_state": {"name": "Idle", "parent": "Root"}}]
    result = run_spec(steps, dry_run=True)
    assert result["ok"] is True
    assert result.get("dry_run") is True


def test_run_spec_empty_steps_succeeds():
    result = run_spec([])
    assert result["ok"] is True
    assert result["steps_completed"] == 0


def test_run_spec_returns_final_spec_state():
    steps = [{"add_state": {"name": "Idle", "parent": "Root"}}]
    result = run_spec(steps)
    assert "spec_state" in result
    names = [s["name"] for s in result["spec_state"]["states"]]
    assert "Idle" in names


# ── CLI integration ───────────────────────────────────────────────────────────

def test_cmd_run_missing_spec_returns_1(tmp_path):
    import subprocess, sys
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "run",
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_run_nonexistent_spec_returns_1(tmp_path):
    import subprocess, sys
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "run",
         "--spec", str(tmp_path / "missing.yaml"),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_run_valid_spec_returns_0(tmp_path):
    import subprocess, sys
    spec = tmp_path / "spec.yaml"
    spec.write_text("steps:\n  - add_state: {name: Idle, parent: Root}\n")
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "run",
         "--spec", str(spec),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_cmd_run_spec_with_error_returns_1(tmp_path):
    import subprocess, sys
    spec = tmp_path / "spec.yaml"
    spec.write_text("steps:\n  - add_state: {name: Idle, parent: NonExistent}\n")
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "run",
         "--spec", str(spec),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_run_result_contains_steps(tmp_path):
    import subprocess, sys
    spec = tmp_path / "spec.yaml"
    spec.write_text(textwrap.dedent("""\
        steps:
          - add_state: {name: Idle, parent: Root}
          - add_state: {name: Patrol, parent: Root}
    """))
    result_path = tmp_path / "result.json"
    subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "run",
         "--spec", str(spec),
         "--result", str(result_path)],
        capture_output=True,
    )
    data = json.loads(result_path.read_text())
    assert "steps_completed" in data


def test_cmd_run_dry_run_returns_0(tmp_path):
    import subprocess, sys
    spec = tmp_path / "spec.yaml"
    spec.write_text("steps:\n  - add_state: {name: Idle, parent: Root}\n")
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "run",
         "--spec", str(spec),
         "--dry-run",
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 0
    data = json.loads(result_path.read_text())
    assert data.get("dry_run") is True
