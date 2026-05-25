"""Tests for ue-auto ai statetree diff (TDD — RED first)."""
import json
import pytest
from pathlib import Path

from ue_auto.commands.ai_statetree import diff_snapshots


# ── fixtures ──────────────────────────────────────────────────────────────────

_SNAP_BASE = {
    "asset": "/Game/AI/ST_Test",
    "states": [
        {"name": "Root", "children": []},
        {"name": "Idle", "children": []},
    ],
    "transitions": [],
    "tasks": [],
}


# ── diff_snapshots ────────────────────────────────────────────────────────────

def test_diff_no_changes():
    diff = diff_snapshots(_SNAP_BASE, _SNAP_BASE)
    assert diff["added_states"] == []
    assert diff["removed_states"] == []
    assert diff["added_transitions"] == []
    assert diff["removed_transitions"] == []


def test_diff_added_state():
    after = {**_SNAP_BASE, "states": _SNAP_BASE["states"] + [{"name": "Patrol", "children": []}]}
    diff = diff_snapshots(_SNAP_BASE, after)
    assert "Patrol" in diff["added_states"]
    assert diff["removed_states"] == []


def test_diff_removed_state():
    after = {**_SNAP_BASE, "states": [_SNAP_BASE["states"][0]]}  # Root only
    diff = diff_snapshots(_SNAP_BASE, after)
    assert "Idle" in diff["removed_states"]
    assert diff["added_states"] == []


def test_diff_added_transition():
    before = {**_SNAP_BASE, "transitions": []}
    after = {**_SNAP_BASE, "transitions": [{"from": "Idle", "to": "Patrol"}]}
    diff = diff_snapshots(before, after)
    assert len(diff["added_transitions"]) == 1
    assert diff["added_transitions"][0]["from"] == "Idle"


def test_diff_removed_transition():
    before = {**_SNAP_BASE, "transitions": [{"from": "Idle", "to": "Patrol"}]}
    after = {**_SNAP_BASE, "transitions": []}
    diff = diff_snapshots(before, after)
    assert len(diff["removed_transitions"]) == 1


def test_diff_added_task():
    before = {**_SNAP_BASE, "tasks": []}
    after = {**_SNAP_BASE, "tasks": [{"state": "Idle", "task": "STT_Wait"}]}
    diff = diff_snapshots(before, after)
    assert len(diff["added_tasks"]) == 1


def test_diff_removed_task():
    before = {**_SNAP_BASE, "tasks": [{"state": "Idle", "task": "STT_Wait"}]}
    after = {**_SNAP_BASE, "tasks": []}
    diff = diff_snapshots(before, after)
    assert len(diff["removed_tasks"]) == 1


def test_diff_has_changed_flag_false_when_no_changes():
    diff = diff_snapshots(_SNAP_BASE, _SNAP_BASE)
    assert diff["changed"] is False


def test_diff_has_changed_flag_true_when_state_added():
    after = {**_SNAP_BASE, "states": _SNAP_BASE["states"] + [{"name": "Patrol", "children": []}]}
    diff = diff_snapshots(_SNAP_BASE, after)
    assert diff["changed"] is True


def test_diff_markdown_contains_added_state_name():
    after = {**_SNAP_BASE, "states": _SNAP_BASE["states"] + [{"name": "Patrol", "children": []}]}
    diff = diff_snapshots(_SNAP_BASE, after)
    assert "Patrol" in diff["markdown"]


def test_diff_markdown_contains_no_changes_when_identical():
    diff = diff_snapshots(_SNAP_BASE, _SNAP_BASE)
    assert "no change" in diff["markdown"].lower() or "변경 없음" in diff["markdown"]


def test_diff_markdown_contains_removed_state():
    after = {**_SNAP_BASE, "states": [_SNAP_BASE["states"][0]]}
    diff = diff_snapshots(_SNAP_BASE, after)
    assert "Idle" in diff["markdown"]


# ── CLI integration ───────────────────────────────────────────────────────────

def test_cmd_diff_missing_args_returns_1(tmp_path):
    import subprocess, sys
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "diff",
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_diff_nonexistent_before_returns_1(tmp_path):
    import subprocess, sys
    after = tmp_path / "after.json"
    after.write_text(json.dumps(_SNAP_BASE))
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "diff",
         "--before", str(tmp_path / "missing.json"),
         "--after", str(after),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1


def test_cmd_diff_identical_snapshots_returns_0(tmp_path):
    import subprocess, sys
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_SNAP_BASE))
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "diff",
         "--before", str(snap), "--after", str(snap),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_cmd_diff_with_changes_returns_0_but_reports_changes(tmp_path):
    import subprocess, sys
    before = tmp_path / "before.json"
    before.write_text(json.dumps(_SNAP_BASE))
    after_data = {**_SNAP_BASE, "states": _SNAP_BASE["states"] + [{"name": "Patrol", "children": []}]}
    after = tmp_path / "after.json"
    after.write_text(json.dumps(after_data))
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "diff",
         "--before", str(before), "--after", str(after),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert data.get("changed") is True


def test_cmd_diff_result_contains_markdown(tmp_path):
    import subprocess, sys
    snap = tmp_path / "snap.json"
    snap.write_text(json.dumps(_SNAP_BASE))
    result_path = tmp_path / "result.json"
    subprocess.run(
        [sys.executable, "-m", "ue_auto", "ai", "statetree", "diff",
         "--before", str(snap), "--after", str(snap),
         "--result", str(result_path)],
        capture_output=True,
    )
    data = json.loads(result_path.read_text())
    assert "markdown" in data
