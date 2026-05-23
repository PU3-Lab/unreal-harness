"""Smoke test: CLI → UnrealEditor-Cmd → UEAutoPingCommandlet → result.json.

Requires:
  - UE_EDITOR_CMD env var pointing to a real UnrealEditor-Cmd binary
  - UE_SMOKE_PROJECT env var pointing to a real .uproject file that has the
    UEAutomationBridge plugin installed

Skip automatically when either env var is absent.
"""
import json
import os
import re
import pytest
from pathlib import Path

from ue_auto.runner import run_commandlet

_NEEDS_UE = pytest.mark.skipif(
    not os.environ.get("UE_EDITOR_CMD") or not os.environ.get("UE_SMOKE_PROJECT"),
    reason="UE_EDITOR_CMD and UE_SMOKE_PROJECT env vars required for smoke test",
)


@_NEEDS_UE
def test_ping_commandlet_writes_ok_result():
    """End-to-end: UEAutoPingCommandlet must write ok=true result.json."""
    project = os.environ["UE_SMOKE_PROJECT"]
    result_path = Path(project).parent / "Saved" / "AutomationReports" / "result.json"

    if result_path.exists():
        result_path.unlink()

    exit_code = run_commandlet(project, "UEAutoPingCommandlet", timeout=120)

    assert exit_code == 0, f"Commandlet exited with {exit_code}"
    assert result_path.exists(), f"result.json not written at {result_path}"

    data = json.loads(result_path.read_text(encoding="utf-8"))
    assert data.get("ok") is True, f"result.json ok=false: {data}"
    assert data.get("action") == "ping"
    assert data.get("message") == "pong"
    assert "timestamp" in data


@_NEEDS_UE
def test_ping_commandlet_result_json_schema():
    """result.json produced by ping commandlet must match the 00_overview §7 schema."""
    project = os.environ["UE_SMOKE_PROJECT"]
    result_path = Path(project).parent / "Saved" / "AutomationReports" / "result.json"

    if result_path.exists():
        result_path.unlink()

    run_commandlet(project, "UEAutoPingCommandlet", timeout=120)

    assert result_path.exists()
    data = json.loads(result_path.read_text(encoding="utf-8"))

    assert isinstance(data.get("ok"), bool)
    assert isinstance(data.get("action"), str)
    assert isinstance(data.get("message"), str)
    assert isinstance(data.get("timestamp"), str)
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", data["timestamp"]), \
        f"timestamp not ISO-8601 UTC: {data['timestamp']}"
