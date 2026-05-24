import json
import pytest
import yaml
from pathlib import Path

from ue_auto.commands.ai_statetree import _cmd_statetree_validate


def _snapshot(states: list[dict], evaluators: list[dict] | None = None) -> dict:
    return {
        "asset_path": "/Game/AI/StateTrees/ST_Test",
        "name": "ST_Test",
        "evaluators": evaluators or [],
        "states": states,
    }


def _write_snapshot(tmp_path, states: list[dict], evaluators: list[dict] | None = None) -> str:
    p = tmp_path / "statetree.snapshot.json"
    p.write_text(json.dumps(_snapshot(states, evaluators=evaluators)))
    return str(p)


def _write_spec(tmp_path, spec: dict) -> str:
    p = tmp_path / "wire.spec.yaml"
    p.write_text(yaml.dump(spec))
    return str(p)


class _Args:
    def __init__(self, **kwargs):
        self.snapshot = kwargs.get("snapshot", None)
        self.spec = kwargs.get("spec", None)
        self.out_md = kwargs.get("out_md", None)
        self.out_json = kwargs.get("out_json", None)
        self.result = kwargs.get("result", "result.json")
        self.dry_run = False
        self.apply = False


_CLEAN_STATES = [
    {"name": "Root", "parent": None, "tasks": [], "transitions": []},
    {
        "name": "Patrol",
        "parent": "Root",
        "tasks": ["MoveToTask"],
        "transitions": [{"target": "Chase", "trigger": "HasTarget"}],
    },
    {
        "name": "Chase",
        "parent": "Root",
        "tasks": ["MoveToTask"],
        "transitions": [{"target": "Patrol", "trigger": "LostTarget"}],
    },
]


# ── missing / not found ───────────────────────────────────────────────────────

def test_validate_missing_snapshot_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "MISSING_SNAPSHOT"


def test_validate_snapshot_not_found_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=str(tmp_path / "nope.json"), result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "SNAPSHOT_NOT_FOUND"


# ── clean tree ────────────────────────────────────────────────────────────────

def test_validate_clean_tree_passes(tmp_path):
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True


# ── dead state ────────────────────────────────────────────────────────────────

def test_validate_dead_state_detected(tmp_path):
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {
            "name": "Patrol",
            "parent": "Root",
            "tasks": [],
            "transitions": [],  # no transition to Orphan
        },
        {
            "name": "Orphan",  # nothing points here
            "parent": "Root",
            "tasks": [],
            "transitions": [],
        },
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    checks = data["checks"]
    dead = [c for c in checks if c["type"] == "DEAD_STATE"]
    assert len(dead) == 1
    assert dead[0]["state"] == "Orphan"


def test_validate_dead_state_excluded_for_root_children_with_no_transitions_into_them_when_root_has_no_transitions(tmp_path):
    """Root-level states (parent=Root) without incoming transitions are NOT dead
    if Root itself has no explicit transitions — the tree starts at Root's children.
    (Idle may trigger NO_EXIT_TRANSITION; that is a separate concern.)
    """
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {"name": "Idle", "parent": "Root", "tasks": [], "transitions": []},
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    _cmd_statetree_validate(args)
    data = json.loads(result_path.read_text())
    dead = [c for c in data.get("checks", []) if c["type"] == "DEAD_STATE"]
    assert len(dead) == 0


# ── missing transition target ─────────────────────────────────────────────────

def test_validate_missing_transition_target_detected(tmp_path):
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {
            "name": "Patrol",
            "parent": "Root",
            "tasks": [],
            "transitions": [{"target": "GhostState", "trigger": "Always"}],
        },
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    checks = data["checks"]
    missing = [c for c in checks if c["type"] == "MISSING_TARGET"]
    assert len(missing) == 1
    assert missing[0]["state"] == "Patrol"
    assert missing[0]["target"] == "GhostState"


# ── multiple violations ───────────────────────────────────────────────────────

def test_validate_multiple_violations(tmp_path):
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {
            "name": "Patrol",
            "parent": "Root",
            "tasks": [],
            "transitions": [{"target": "NoSuchState", "trigger": "t"}],
        },
        # Orphan: DEAD_STATE (not reachable) + NO_EXIT_TRANSITION (no transitions)
        {"name": "Orphan", "parent": "Root", "tasks": [], "transitions": []},
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    types = {c["type"] for c in data["checks"]}
    assert "DEAD_STATE" in types
    assert "MISSING_TARGET" in types
    assert "NO_EXIT_TRANSITION" in types


# ── output files ─────────────────────────────────────────────────────────────

def test_validate_writes_validation_json(tmp_path):
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES)
    out_json = str(tmp_path / "validation.json")
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, out_json=out_json, result=str(result_path))
    _cmd_statetree_validate(args)
    data = json.loads(Path(out_json).read_text())
    assert "ok" in data
    assert "violations" in data


def test_validate_writes_validation_md(tmp_path):
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {
            "name": "Patrol",
            "parent": "Root",
            "tasks": [],
            "transitions": [{"target": "Ghost", "trigger": "t"}],
        },
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    out_md = str(tmp_path / "validation.md")
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, out_md=out_md, result=str(result_path))
    _cmd_statetree_validate(args)
    content = Path(out_md).read_text()
    assert "MISSING_TARGET" in content
    assert "Ghost" in content


# ── NO_EXIT_TRANSITION ────────────────────────────────────────────────────────

def test_validate_no_exit_transition_leaf_flagged(tmp_path):
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {"name": "Patrol", "parent": "Root", "tasks": [], "transitions": [{"target": "Chase", "trigger": "t"}]},
        {"name": "Chase", "parent": "Root", "tasks": [], "transitions": [{"target": "Patrol", "trigger": "t"}]},
        {"name": "Dead", "parent": "Root", "tasks": [], "transitions": []},  # leaf, no exit
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    no_exit = [c for c in data["checks"] if c["type"] == "NO_EXIT_TRANSITION"]
    assert len(no_exit) == 1
    assert no_exit[0]["state"] == "Dead"


def test_validate_no_exit_transition_container_not_flagged(tmp_path):
    """Container states (those that ARE parents of other states) are not flagged."""
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {"name": "Combat", "parent": "Root", "tasks": [], "transitions": []},  # container
        {"name": "Melee", "parent": "Combat", "tasks": [], "transitions": [{"target": "Ranged", "trigger": "t"}]},
        {"name": "Ranged", "parent": "Combat", "tasks": [], "transitions": [{"target": "Melee", "trigger": "t"}]},
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    _cmd_statetree_validate(args)
    data = json.loads(result_path.read_text())
    no_exit = [c for c in data.get("checks", []) if c["type"] == "NO_EXIT_TRANSITION"]
    assert len(no_exit) == 0


# ── INVALID_EVALUATOR ─────────────────────────────────────────────────────────

def test_validate_invalid_evaluator_none_class_flagged(tmp_path):
    evaluators = [{"class": "None"}]
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES, evaluators=evaluators)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    ev_violations = [c for c in data["checks"] if c["type"] == "INVALID_EVALUATOR"]
    assert len(ev_violations) == 1


def test_validate_invalid_evaluator_empty_class_flagged(tmp_path):
    evaluators = [{"class": ""}]
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES, evaluators=evaluators)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    ev_violations = [c for c in data["checks"] if c["type"] == "INVALID_EVALUATOR"]
    assert len(ev_violations) == 1


def test_validate_valid_evaluator_passes(tmp_path):
    evaluators = [{"class": "MyEvaluator"}]
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES, evaluators=evaluators)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 0
    data = json.loads(result_path.read_text())
    ev_violations = [c for c in data.get("checks", []) if c["type"] == "INVALID_EVALUATOR"]
    assert len(ev_violations) == 0


# ── DUPLICATE_STATE ───────────────────────────────────────────────────────────

def test_validate_duplicate_state_names_flagged(tmp_path):
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {"name": "Patrol", "parent": "Root", "tasks": [], "transitions": [{"target": "Patrol2", "trigger": "t"}]},
        {"name": "Patrol", "parent": "Root", "tasks": [], "transitions": [{"target": "Patrol", "trigger": "t"}]},
        {"name": "Patrol2", "parent": "Root", "tasks": [], "transitions": [{"target": "Patrol", "trigger": "t"}]},
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    dup = [c for c in data["checks"] if c["type"] == "DUPLICATE_STATE"]
    assert len(dup) == 1
    assert dup[0]["state"] == "Patrol"


def test_validate_unique_names_no_duplicate_violation(tmp_path):
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    _cmd_statetree_validate(args)
    data = json.loads(result_path.read_text())
    dup = [c for c in data.get("checks", []) if c["type"] == "DUPLICATE_STATE"]
    assert len(dup) == 0


# ── SPEC_MISMATCH ─────────────────────────────────────────────────────────────

def test_validate_no_spec_skips_mismatch_check(tmp_path):
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 0
    data = json.loads(result_path.read_text())
    mismatch = [c for c in data.get("checks", []) if c["type"] == "SPEC_MISMATCH"]
    assert len(mismatch) == 0


def test_validate_spec_matches_snapshot_passes(tmp_path):
    spec = {"states": [{"name": "Root"}, {"name": "Patrol"}, {"name": "Chase"}]}
    spec_path = _write_spec(tmp_path, spec)
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, spec=spec_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 0
    data = json.loads(result_path.read_text())
    mismatch = [c for c in data.get("checks", []) if c["type"] == "SPEC_MISMATCH"]
    assert len(mismatch) == 0


def test_validate_spec_missing_state_flagged(tmp_path):
    spec = {"states": [{"name": "Root"}, {"name": "Patrol"}, {"name": "Chase"}, {"name": "Flee"}]}
    spec_path = _write_spec(tmp_path, spec)
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, spec=spec_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    mismatch = [c for c in data["checks"] if c["type"] == "SPEC_MISMATCH"]
    assert len(mismatch) == 1
    assert mismatch[0]["state"] == "Flee"


def test_validate_spec_extra_state_in_snapshot_flagged(tmp_path):
    spec = {"states": [{"name": "Root"}, {"name": "Patrol"}]}
    spec_path = _write_spec(tmp_path, spec)
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, spec=spec_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    mismatch = [c for c in data["checks"] if c["type"] == "SPEC_MISMATCH"]
    extra = [c for c in mismatch if c["state"] == "Chase"]
    assert len(extra) == 1


def test_validate_spec_not_found_returns_error(tmp_path):
    snapshot_path = _write_snapshot(tmp_path, _CLEAN_STATES)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, spec=str(tmp_path / "nonexistent.yaml"), result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "SPEC_NOT_FOUND"
