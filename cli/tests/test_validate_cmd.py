import json
from pathlib import Path

import pytest

from ue_auto.commands.validate_cmd import _cmd_validate_all


class _Args:
    def __init__(self, **kw):
        self.project = kw.get("project", None)
        self.result = kw.get("result", "Saved/AutomationReports/result.json")
        self.out = kw.get("out", None)


def test_cmd_validate_all_missing_project(tmp_path):
    result_path = tmp_path / "result.json"
    ret = _cmd_validate_all(_Args(project=None, result=str(result_path)))
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_validate_all_stub_returns_warn(tmp_path):
    result_path = tmp_path / "result.json"
    ret = _cmd_validate_all(_Args(project="MyGame.uproject", result=str(result_path)))
    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert "no domain validators" in data.get("message", "").lower()
