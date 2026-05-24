"""Tests for ue-auto ai statetree create (TDD — RED first)."""
import argparse
import subprocess
import sys
import textwrap
from unittest.mock import MagicMock, patch
import pytest
from pathlib import Path

from ue_auto.commands.ai_statetree import (
    generate_create_script,
    parse_create_spec,
)
import ue_auto.commands.ai_statetree as st_mod


# ── fixtures ──────────────────────────────────────────────────────────────────

def _spec():
    return {
        "character": {
            "name": "BP_EnemyCharacter",
            "content_path": "/Game/AI/Characters",
            "parent_class": "Character",
        },
        "statetree": {
            "name": "ST_EnemyAI",
            "content_path": "/Game/AI/StateTrees",
        },
    }


# ── parse_create_spec ─────────────────────────────────────────────────────────

def test_parse_create_spec_valid(tmp_path):
    yaml_text = textwrap.dedent("""\
        character:
          name: BP_EnemyCharacter
          content_path: /Game/AI/Characters
          parent_class: Character
        statetree:
          name: ST_EnemyAI
          content_path: /Game/AI/StateTrees
    """)
    f = tmp_path / "spec.yaml"
    f.write_text(yaml_text)
    spec = parse_create_spec(str(f))
    assert spec["character"]["name"] == "BP_EnemyCharacter"
    assert spec["statetree"]["name"] == "ST_EnemyAI"


def test_parse_create_spec_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_create_spec(str(tmp_path / "missing.yaml"))


def test_parse_create_spec_missing_character_key_raises(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("statetree:\n  name: ST_X\n  content_path: /Game/AI\n")
    with pytest.raises(ValueError, match="character"):
        parse_create_spec(str(f))


def test_parse_create_spec_missing_statetree_key_raises(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("character:\n  name: BP_X\n  content_path: /Game/AI\n")
    with pytest.raises(ValueError, match="statetree"):
        parse_create_spec(str(f))


def test_parse_create_spec_defaults_parent_class(tmp_path):
    yaml_text = textwrap.dedent("""\
        character:
          name: BP_EnemyCharacter
          content_path: /Game/AI/Characters
        statetree:
          name: ST_EnemyAI
          content_path: /Game/AI/StateTrees
    """)
    f = tmp_path / "spec.yaml"
    f.write_text(yaml_text)
    spec = parse_create_spec(str(f))
    assert spec["character"]["parent_class"] == "Character"


# ── generate_create_script ────────────────────────────────────────────────────

def test_script_imports_unreal():
    script = generate_create_script(_spec())
    assert "import unreal" in script


def test_script_creates_statetree_asset():
    script = generate_create_script(_spec())
    assert "ST_EnemyAI" in script
    assert "/Game/AI/StateTrees" in script
    assert "StateTree" in script


def test_script_creates_blueprint_character():
    script = generate_create_script(_spec())
    assert "BP_EnemyCharacter" in script
    assert "/Game/AI/Characters" in script
    assert "BlueprintFactory" in script


def test_script_sets_parent_class():
    script = generate_create_script(_spec())
    assert "Character" in script
    assert "parent_class" in script


def test_script_adds_statetree_component():
    script = generate_create_script(_spec())
    assert "StateTreeComponent" in script
    assert "add_new_subobject" in script


def test_script_uses_engine_subsystem_not_editor_subsystem():
    # SubobjectDataSubsystem is UEngineSubsystem — get_editor_subsystem crashes.
    script = generate_create_script(_spec())
    assert "get_engine_subsystem" in script
    assert "get_editor_subsystem" not in script


def test_script_checks_fail_reason_not_is_valid():
    # SubobjectDataHandle has no is_valid() in Python bindings; use fail_reason.
    script = generate_create_script(_spec())
    assert "fail_reason" in script
    assert "is_valid" not in script


def test_script_assigns_statetree_to_component():
    script = generate_create_script(_spec())
    assert "state_tree_ref" in script


def test_script_compiles_blueprint():
    script = generate_create_script(_spec())
    assert "compile_blueprint" in script


def test_script_saves_assets():
    script = generate_create_script(_spec())
    assert "save_asset" in script


def test_script_uses_custom_names():
    spec = {
        "character": {
            "name": "BP_BossCharacter",
            "content_path": "/Game/Boss",
            "parent_class": "Pawn",
        },
        "statetree": {
            "name": "ST_BossAI",
            "content_path": "/Game/Boss/AI",
        },
    }
    script = generate_create_script(spec)
    assert "BP_BossCharacter" in script
    assert "ST_BossAI" in script
    assert "/Game/Boss/AI" in script
    assert "Pawn" in script


def test_script_prints_result_paths():
    script = generate_create_script(_spec())
    assert "print(" in script


def test_script_writes_result_json_when_path_given():
    script = generate_create_script(_spec(), result_json_path="/tmp/result.json")
    assert "/tmp/result.json" in script
    assert "json.dump" in script


def test_script_includes_validation_checks():
    script = generate_create_script(_spec(), result_json_path="/tmp/r.json")
    assert "statetree_created" in script
    assert "blueprint_created" in script
    assert "component_added" in script
    assert "statetree_assigned" in script
    assert "assets_saved" in script


def test_script_validation_check_all_ok_field():
    script = generate_create_script(_spec(), result_json_path="/tmp/r.json")
    assert '"ok"' in script or "'ok'" in script


# ── unit: _cmd_statetree_create with project (mocked UE) ─────────────────────

def _make_args(tmp_path, spec_file, project=None, dry_run=False):
    return argparse.Namespace(
        spec=str(spec_file),
        project=project,
        out=str(tmp_path),
        result=None,
        out_md=None,
        out_json=None,
        dry_run=dry_run,
        apply=not dry_run,
    )


def _write_spec(tmp_path):
    yaml_text = textwrap.dedent("""\
        character:
          name: BP_EnemyCharacter
          content_path: /Game/AI/Characters
          parent_class: Character
        statetree:
          name: ST_EnemyAI
          content_path: /Game/AI/StateTrees
    """)
    f = tmp_path / "spec.yaml"
    f.write_text(yaml_text)
    return f


def test_cmd_create_apply_no_project_writes_script_only(tmp_path):
    spec_file = _write_spec(tmp_path)
    args = _make_args(tmp_path, spec_file, project=None)
    rc = st_mod._cmd_statetree_create(args)
    assert rc == 0
    assert (tmp_path / "statetree_create.py").exists()


def test_cmd_create_apply_with_project_calls_ue(tmp_path):
    spec_file = _write_spec(tmp_path)
    result_json = tmp_path / "statetree_create.result.json"
    result_json.write_text('{"ok": true, "checks": [], "assets": []}')

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = ""

    with patch.object(st_mod, "find_editor", return_value="/fake/UnrealEditor-Cmd"):
        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            args = _make_args(tmp_path, spec_file, project="/fake/MyProject.uproject")
            rc = st_mod._cmd_statetree_create(args)

    assert rc == 0
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert "/fake/UnrealEditor-Cmd" in cmd
    assert any("-ExecutePythonScript" in a for a in cmd)


def test_cmd_create_apply_with_project_reads_result_json(tmp_path):
    spec_file = _write_spec(tmp_path)
    result_json = tmp_path / "statetree_create.result.json"
    result_json.write_text('{"ok": false, "checks": [{"name": "statetree_created", "ok": false}], "assets": []}')

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stderr = ""

    with patch.object(st_mod, "find_editor", return_value="/fake/UnrealEditor-Cmd"):
        with patch("subprocess.run", return_value=mock_proc):
            args = _make_args(tmp_path, spec_file, project="/fake/MyProject.uproject")
            rc = st_mod._cmd_statetree_create(args)

    assert rc == 1


def test_cmd_create_apply_ue_failure_returns_1(tmp_path):
    spec_file = _write_spec(tmp_path)

    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stderr = "Some UE error"

    with patch.object(st_mod, "find_editor", return_value="/fake/UnrealEditor-Cmd"):
        with patch("subprocess.run", return_value=mock_proc):
            args = _make_args(tmp_path, spec_file, project="/fake/MyProject.uproject")
            rc = st_mod._cmd_statetree_create(args)

    assert rc == 1


def test_cmd_create_apply_no_editor_returns_1(tmp_path):
    spec_file = _write_spec(tmp_path)

    with patch.object(st_mod, "find_editor", return_value=None):
        args = _make_args(tmp_path, spec_file, project="/fake/MyProject.uproject")
        rc = st_mod._cmd_statetree_create(args)

    assert rc == 1


# ── CLI integration ───────────────────────────────────────────────────────────

def test_cli_create_missing_spec_returns_1():
    result = subprocess.run(
        [sys.executable, "-m", "ue_auto",
         "ai", "statetree", "create"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0


def test_cli_create_dry_run_does_not_write_script(tmp_path):
    yaml_text = textwrap.dedent("""\
        character:
          name: BP_EnemyCharacter
          content_path: /Game/AI/Characters
          parent_class: Character
        statetree:
          name: ST_EnemyAI
          content_path: /Game/AI/StateTrees
    """)
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(yaml_text)

    result = subprocess.run(
        [sys.executable, "-m", "ue_auto",
         "ai", "statetree", "create",
         "--spec", str(spec_file),
         "--out", str(tmp_path),
         "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert not (tmp_path / "statetree_create.py").exists()


def test_cli_create_apply_writes_script(tmp_path):
    yaml_text = textwrap.dedent("""\
        character:
          name: BP_EnemyCharacter
          content_path: /Game/AI/Characters
          parent_class: Character
        statetree:
          name: ST_EnemyAI
          content_path: /Game/AI/StateTrees
    """)
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(yaml_text)

    result = subprocess.run(
        [sys.executable, "-m", "ue_auto",
         "ai", "statetree", "create",
         "--spec", str(spec_file),
         "--out", str(tmp_path),
         "--apply"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    script_file = tmp_path / "statetree_create.py"
    assert script_file.exists()
    content = script_file.read_text()
    assert "import unreal" in content
    assert "BP_EnemyCharacter" in content
    assert "ST_EnemyAI" in content
