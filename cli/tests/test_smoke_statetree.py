"""Smoke tests: CLI → UnrealEditor-Cmd → StateTree commandlets.

Requires:
  - UE_EDITOR_CMD env var pointing to a real UnrealEditor-Cmd binary
  - UE_SMOKE_PROJECT env var pointing to a real .uproject with UEAutomationBridge plugin
  - Content/AI/StateTrees/ST_EnemyAI.uasset present in the project

All tests skip automatically when either env var is absent.

Test design:
  - Each test is self-contained (no shared file state across tests).
  - Wire tests modify ST_EnemyAI to a known-good Idle/Flee state; they can run
    in any order without leaving the asset in a broken state.
  - The pipeline smoke test (wire → snapshot → validate) verifies the full
    Python-to-C++ round-trip in a single test.
"""
import json
import os
import pytest
from pathlib import Path

from ue_auto.commands.ai_statetree import (
    _cmd_statetree_snapshot,
    _cmd_statetree_wire,
    validate_statetree,
)

_NEEDS_UE = pytest.mark.skipif(
    not os.environ.get("UE_EDITOR_CMD") or not os.environ.get("UE_SMOKE_PROJECT"),
    reason="UE_EDITOR_CMD and UE_SMOKE_PROJECT env vars required for smoke tests",
)

_ASSET = "/Game/AI/StateTrees/ST_EnemyAI"

_WIRE_SPEC_YAML = """\
statetree:
  asset: /Game/AI/StateTrees/ST_EnemyAI
  states:
    - name: Idle
      transitions:
        - trigger: OnTick
          target: Flee
          conditions:
            - class: IsPlayerNear
              radius: 500.0
    - name: Flee
      tasks:
        - class: FleeTask
          flee_distance: 800.0
      transitions:
        - trigger: OnTick
          target: Idle
          conditions:
            - class: IsPlayerNear
              radius: 500.0
              invert: true
"""


class _SnapArgs:
    def __init__(self, project: str, out: str, result: str) -> None:
        self.project = project
        self.asset = _ASSET
        self.out = out
        self.result = result
        self.dry_run = False


class _WireArgs:
    def __init__(
        self,
        project: str,
        out: str,
        result: str,
        spec: str | None = None,
        asset: str | None = None,
    ) -> None:
        self.project = project
        self.asset = asset
        self.out = out
        self.result = result
        self.spec = spec
        self.dry_run = False


# ── snapshot ──────────────────────────────────────────────────────────────────

@_NEEDS_UE
def test_statetree_snapshot_commandlet_writes_json(tmp_path):
    """StateTreeSnapshotCommandlet must write a JSON file on exit 0."""
    project = os.environ["UE_SMOKE_PROJECT"]
    snap_path = tmp_path / "ST_EnemyAI.snapshot.json"
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_snapshot(_SnapArgs(project, str(snap_path), str(result_path)))

    assert ret == 0, f"snapshot exited with {ret}"
    assert snap_path.exists(), "snapshot JSON not written"

    data = json.loads(snap_path.read_text(encoding="utf-8"))
    assert "states" in data, f"snapshot missing 'states': {list(data.keys())}"
    assert "asset_path" in data, f"snapshot missing 'asset_path': {list(data.keys())}"


@_NEEDS_UE
def test_statetree_snapshot_json_schema(tmp_path):
    """Snapshot JSON must have the required fields and correct types."""
    project = os.environ["UE_SMOKE_PROJECT"]
    snap_path = tmp_path / "ST_EnemyAI.snapshot.json"
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_snapshot(_SnapArgs(project, str(snap_path), str(result_path)))
    assert ret == 0, f"snapshot exited with {ret}"

    data = json.loads(snap_path.read_text(encoding="utf-8"))
    assert isinstance(data.get("asset_path"), str)
    assert isinstance(data.get("name"), str)
    assert isinstance(data.get("states"), list)
    assert isinstance(data.get("evaluators"), list)

    for state in data["states"]:
        assert "name" in state, f"state entry missing 'name': {state}"
        assert "transitions" in state, f"state '{state['name']}' missing 'transitions'"
        assert "tasks" in state, f"state '{state['name']}' missing 'tasks'"


# ── wire ──────────────────────────────────────────────────────────────────────

@_NEEDS_UE
def test_statetree_wire_commandlet_hardcoded(tmp_path):
    """StateTreeWireCommandlet (no spec) writes ok=true and compiles the asset."""
    project = os.environ["UE_SMOKE_PROJECT"]
    out_path = tmp_path / "wire.result.json"
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_wire(
        _WireArgs(project, str(out_path), str(result_path), asset=_ASSET)
    )

    assert ret == 0, f"wire exited with {ret}"
    result_data = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_data.get("ok") is True, f"wire ok=false: {result_data}"


@_NEEDS_UE
def test_statetree_wire_commandlet_with_spec(tmp_path):
    """StateTreeWireCommandlet with YAML spec wires Idle/Flee and compiles ok."""
    project = os.environ["UE_SMOKE_PROJECT"]
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text(_WIRE_SPEC_YAML, encoding="utf-8")

    out_path = tmp_path / "wire.result.json"
    result_path = tmp_path / "result.json"

    ret = _cmd_statetree_wire(
        _WireArgs(project, str(out_path), str(result_path), spec=str(spec_file))
    )

    assert ret == 0, f"wire-with-spec exited with {ret}"
    result_data = json.loads(result_path.read_text(encoding="utf-8"))
    assert result_data.get("ok") is True, f"wire ok=false: {result_data}"


# ── full pipeline: wire → snapshot → validate ─────────────────────────────────

@_NEEDS_UE
def test_statetree_full_pipeline(tmp_path):
    """Wire spec → snapshot → validate: full round-trip must pass clean."""
    project = os.environ["UE_SMOKE_PROJECT"]

    # Step 1: wire to a known-good Idle/Flee layout
    spec_file = tmp_path / "wire.spec.yaml"
    spec_file.write_text(_WIRE_SPEC_YAML, encoding="utf-8")
    wire_out = tmp_path / "wire.result.json"
    wire_result = tmp_path / "wire_cmd.result.json"

    wire_ret = _cmd_statetree_wire(
        _WireArgs(project, str(wire_out), str(wire_result), spec=str(spec_file))
    )
    assert wire_ret == 0, "wire step failed — cannot continue pipeline test"

    # Step 2: snapshot the freshly-wired asset
    snap_path = tmp_path / "ST_EnemyAI.snapshot.json"
    snap_result = tmp_path / "snap_cmd.result.json"

    snap_ret = _cmd_statetree_snapshot(
        _SnapArgs(project, str(snap_path), str(snap_result))
    )
    assert snap_ret == 0, "snapshot step failed"

    snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    states = snapshot.get("states", [])
    assert len(states) == 2, f"expected 2 states after wiring, got {len(states)}: {[s['name'] for s in states]}"

    # Step 3: validate — a freshly-wired Idle/Flee tree must have no violations
    report = validate_statetree(snapshot)
    assert report["violation_count"] == 0, (
        f"validation violations after wiring: {report['violations']}"
    )
