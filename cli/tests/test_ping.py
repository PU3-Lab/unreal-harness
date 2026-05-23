"""Tests for ai_statetree ping command behavior."""
import argparse
import json
import os
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch

from ue_auto.commands.ai_statetree import _cmd_ping


def _make_ping_args(project: Path, result_path: Path) -> argparse.Namespace:
    ns = argparse.Namespace()
    ns.project = str(project)
    ns.result = str(result_path)
    ns.out = None
    ns.out_md = None
    return ns


def test_ping_fails_when_project_arg_missing():
    """ping must return 1 and write MISSING_PROJECT result when --project is absent."""
    ns = argparse.Namespace()
    ns.project = None
    ns.result = "/tmp/test_missing_result.json"
    ns.out = None
    ns.out_md = None

    exit_code = _cmd_ping(ns)

    assert exit_code == 1
    data = json.loads(Path(ns.result).read_text())
    assert data["ok"] is False
    assert data["error"]["code"] == "MISSING_PROJECT"


def test_ping_fails_on_stale_result_json(tmp_path):
    """A stale result.json from a previous run must not cause a false PASS.

    Scenario: commandlet exits 0 (appears to succeed) but fails to write a new
    result.json. The stale file with ok=true must NOT be treated as a fresh result.
    """
    uproject = tmp_path / "Test.uproject"
    uproject.touch()

    reports_dir = tmp_path / "Saved" / "AutomationReports"
    reports_dir.mkdir(parents=True)
    stale = reports_dir / "result.json"
    stale.write_text(json.dumps({"ok": True, "action": "ping", "message": "old run"}))

    result_out = tmp_path / "cli_result.json"

    # Commandlet exits 0 but writes nothing (simulates SaveStringToFile failure)
    fake_proc = type("P", (), {"returncode": 0})()

    with patch("ue_auto.runner.find_editor", return_value="/fake/UnrealEditor-Cmd"), \
         patch("subprocess.run", return_value=fake_proc):
        exit_code = _cmd_ping(_make_ping_args(uproject, result_out))

    assert exit_code == 1


def test_ping_passes_when_commandlet_writes_ok_result(tmp_path):
    """ping must return 0 when commandlet exits 0 and writes ok=true result.json."""
    uproject = tmp_path / "Test.uproject"
    uproject.touch()

    reports_dir = tmp_path / "Saved" / "AutomationReports"
    reports_dir.mkdir(parents=True)
    fresh = reports_dir / "result.json"

    result_out = tmp_path / "cli_result.json"

    fake_proc = type("P", (), {"returncode": 0})()

    def fake_run(cmd, **kwargs):
        fresh.write_text(json.dumps({"ok": True, "action": "ping", "message": "pong"}))
        return fake_proc

    with patch("ue_auto.runner.find_editor", return_value="/fake/UnrealEditor-Cmd"), \
         patch("subprocess.run", side_effect=fake_run):
        exit_code = _cmd_ping(_make_ping_args(uproject, result_out))

    assert exit_code == 0
