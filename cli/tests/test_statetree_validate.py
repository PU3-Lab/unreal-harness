import json
import pytest
from pathlib import Path

from ue_auto.commands.ai_statetree import _cmd_statetree_validate


def _snapshot(states: list[dict]) -> dict:
    return {
        "asset_path": "/Game/AI/StateTrees/ST_Test",
        "name": "ST_Test",
        "states": states,
    }


def _write_snapshot(tmp_path, states: list[dict]) -> str:
    p = tmp_path / "statetree.snapshot.json"
    p.write_text(json.dumps(_snapshot(states)))
    return str(p)


class _Args:
    def __init__(self, **kwargs):
        self.snapshot = kwargs.get("snapshot", None)
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
    if Root itself has no explicit transitions — the tree starts at Root's children."""
    states = [
        {"name": "Root", "parent": None, "tasks": [], "transitions": []},
        {"name": "Idle", "parent": "Root", "tasks": [], "transitions": []},
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 0


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
        {"name": "Orphan", "parent": "Root", "tasks": [], "transitions": []},
    ]
    snapshot_path = _write_snapshot(tmp_path, states)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_validate(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert len(data["checks"]) == 2


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
