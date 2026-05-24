import json
import pytest
from pathlib import Path

from ue_auto.commands.ai_statetree import _cmd_statetree_report


_SNAPSHOT = {
    "asset_path": "/Game/AI/StateTrees/ST_Enemy",
    "name": "ST_Enemy",
    "states": [
        {
            "name": "Root",
            "parent": None,
            "tasks": [],
            "transitions": [],
        },
        {
            "name": "Patrol",
            "parent": "Root",
            "tasks": ["FindPatrolPointTask", "MoveToTask"],
            "transitions": [{"target": "Chase", "trigger": "HasTarget"}],
        },
        {
            "name": "Chase",
            "parent": "Root",
            "tasks": ["MoveToTask"],
            "transitions": [{"target": "Patrol", "trigger": "LostTarget"}],
        },
    ],
}


class _Args:
    def __init__(self, **kwargs):
        self.snapshot = kwargs.get("snapshot", None)
        self.out = kwargs.get("out", None)
        self.out_md = kwargs.get("out_md", None)
        self.result = kwargs.get("result", "result.json")
        self.dry_run = False
        self.apply = False


# ── missing snapshot ──────────────────────────────────────────────────────────

def test_report_missing_snapshot_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(result=str(result_path))
    ret = _cmd_statetree_report(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "MISSING_SNAPSHOT"


def test_report_snapshot_not_found_returns_1(tmp_path):
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=str(tmp_path / "nonexistent.json"), result=str(result_path))
    ret = _cmd_statetree_report(args)
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["error"]["code"] == "SNAPSHOT_NOT_FOUND"


# ── successful report ─────────────────────────────────────────────────────────

def _make_snapshot(tmp_path) -> str:
    p = tmp_path / "statetree.snapshot.json"
    p.write_text(json.dumps(_SNAPSHOT))
    return str(p)


def test_report_writes_result_ok(tmp_path):
    snapshot_path = _make_snapshot(tmp_path)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_report(args)
    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_report_markdown_contains_asset_name(tmp_path):
    snapshot_path = _make_snapshot(tmp_path)
    out_md = str(tmp_path / "report.md")
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, out_md=out_md, result=str(result_path))
    _cmd_statetree_report(args)
    content = Path(out_md).read_text()
    assert "ST_Enemy" in content


def test_report_markdown_shows_state_count(tmp_path):
    snapshot_path = _make_snapshot(tmp_path)
    out_md = str(tmp_path / "report.md")
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, out_md=out_md, result=str(result_path))
    _cmd_statetree_report(args)
    content = Path(out_md).read_text()
    assert "3" in content  # 3 states total


def test_report_markdown_lists_states(tmp_path):
    snapshot_path = _make_snapshot(tmp_path)
    out_md = str(tmp_path / "report.md")
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, out_md=out_md, result=str(result_path))
    _cmd_statetree_report(args)
    content = Path(out_md).read_text()
    assert "Patrol" in content
    assert "Chase" in content


def test_report_markdown_lists_tasks(tmp_path):
    snapshot_path = _make_snapshot(tmp_path)
    out_md = str(tmp_path / "report.md")
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, out_md=out_md, result=str(result_path))
    _cmd_statetree_report(args)
    content = Path(out_md).read_text()
    assert "FindPatrolPointTask" in content
    assert "MoveToTask" in content


def test_report_markdown_lists_transitions(tmp_path):
    snapshot_path = _make_snapshot(tmp_path)
    out_md = str(tmp_path / "report.md")
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, out_md=out_md, result=str(result_path))
    _cmd_statetree_report(args)
    content = Path(out_md).read_text()
    assert "Chase" in content
    assert "HasTarget" in content


def test_report_no_out_still_returns_0(tmp_path):
    snapshot_path = _make_snapshot(tmp_path)
    result_path = tmp_path / "result.json"
    args = _Args(snapshot=snapshot_path, result=str(result_path))
    ret = _cmd_statetree_report(args)
    assert ret == 0
