"""Tests for ue-auto cpp generate-class (TDD — RED first)."""
import textwrap
import pytest
from pathlib import Path

from ue_auto.commands.cpp_cmd import (
    generate_header,
    generate_source,
    build_property_decl,
    build_function_decl,
    parse_spec,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _actor_spec(**overrides):
    spec = {
        "class": {
            "name": "MyActor",
            "type": "Actor",
            "module": "MyGame",
            "tick": True,
        },
        "properties": [],
        "functions": [],
    }
    spec["class"].update(overrides)
    return spec


def _component_spec(**overrides):
    spec = {
        "class": {
            "name": "HealthComponent",
            "type": "ActorComponent",
            "module": "MyGame",
            "tick": False,
        },
        "properties": [
            {
                "name": "MaxHealth",
                "type": "float",
                "default": 100.0,
                "metadata": {"EditAnywhere": True, "BlueprintReadOnly": True, "Category": "Health"},
            }
        ],
        "functions": [
            {
                "name": "ApplyDamage",
                "return_type": "void",
                "params": [{"name": "DamageAmount", "type": "float"}],
                "metadata": {"BlueprintCallable": True, "Category": "Health"},
            }
        ],
    }
    spec["class"].update(overrides)
    return spec


def _dataasset_spec(**overrides):
    spec = {
        "class": {"name": "WeaponData", "type": "DataAsset", "module": "MyGame"},
        "properties": [
            {
                "name": "Damage",
                "type": "float",
                "default": 10.0,
                "metadata": {"EditDefaultsOnly": True, "BlueprintReadOnly": True, "Category": "Weapon"},
            }
        ],
        "functions": [],
    }
    spec["class"].update(overrides)
    return spec


def _interface_spec(**overrides):
    spec = {
        "class": {"name": "Interactable", "type": "Interface", "module": "MyGame"},
        "properties": [],
        "functions": [
            {
                "name": "Interact",
                "return_type": "void",
                "params": [],
                "metadata": {"BlueprintNativeEvent": True, "BlueprintCallable": True, "Category": "Interaction"},
            }
        ],
    }
    spec["class"].update(overrides)
    return spec


# ── parse_spec ────────────────────────────────────────────────────────────────

def test_parse_spec_from_yaml(tmp_path):
    yaml_text = textwrap.dedent("""\
        class:
          name: HeroActor
          type: Actor
          module: MyGame
          tick: false
        properties: []
        functions: []
    """)
    f = tmp_path / "hero.yaml"
    f.write_text(yaml_text)
    spec = parse_spec(str(f))
    assert spec["class"]["name"] == "HeroActor"
    assert spec["class"]["type"] == "Actor"
    assert spec["class"]["tick"] is False


def test_parse_spec_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_spec(str(tmp_path / "missing.yaml"))


def test_parse_spec_missing_class_key_raises(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("properties: []\nfunctions: []\n")
    with pytest.raises(ValueError, match="class"):
        parse_spec(str(f))


# ── build_property_decl ───────────────────────────────────────────────────────

def test_property_decl_basic():
    prop = {
        "name": "MaxHealth",
        "type": "float",
        "metadata": {"EditAnywhere": True, "BlueprintReadWrite": True, "Category": "Health"},
    }
    decl = build_property_decl(prop)
    assert "UPROPERTY" in decl
    assert "EditAnywhere" in decl
    assert "BlueprintReadWrite" in decl
    assert 'Category = "Health"' in decl
    assert "float" in decl
    assert "MaxHealth" in decl


def test_property_decl_no_metadata():
    prop = {"name": "Score", "type": "int32", "metadata": {}}
    decl = build_property_decl(prop)
    assert "UPROPERTY()" in decl
    assert "int32" in decl
    assert "Score" in decl


def test_property_decl_with_default_comment():
    prop = {"name": "Speed", "type": "float", "default": 600.0, "metadata": {}}
    decl = build_property_decl(prop)
    assert "Speed" in decl


# ── build_function_decl ───────────────────────────────────────────────────────

def test_function_decl_blueprintcallable():
    fn = {
        "name": "ApplyDamage",
        "return_type": "void",
        "params": [{"name": "DamageAmount", "type": "float"}],
        "metadata": {"BlueprintCallable": True, "Category": "Health"},
    }
    decl = build_function_decl(fn)
    assert "UFUNCTION" in decl
    assert "BlueprintCallable" in decl
    assert 'Category = "Health"' in decl
    assert "void" in decl
    assert "ApplyDamage" in decl
    assert "float DamageAmount" in decl


def test_function_decl_no_params():
    fn = {"name": "Die", "return_type": "void", "params": [], "metadata": {}}
    decl = build_function_decl(fn)
    assert "Die()" in decl


def test_function_decl_multiple_params():
    fn = {
        "name": "SetStats",
        "return_type": "void",
        "params": [
            {"name": "Health", "type": "float"},
            {"name": "Armor", "type": "int32"},
        ],
        "metadata": {},
    }
    decl = build_function_decl(fn)
    assert "float Health" in decl
    assert "int32 Armor" in decl


# ── generate_header — Actor ───────────────────────────────────────────────────

def test_actor_header_includes_generated_h():
    h = generate_header(_actor_spec())
    assert '#include "MyActor.generated.h"' in h


def test_actor_header_class_declaration():
    h = generate_header(_actor_spec())
    assert "class MYGAME_API AMyActor : public AActor" in h


def test_actor_header_generated_body():
    h = generate_header(_actor_spec())
    assert "GENERATED_BODY()" in h


def test_actor_header_uclass_macro():
    h = generate_header(_actor_spec())
    assert "UCLASS(" in h


def test_actor_header_tick_enabled():
    h = generate_header(_actor_spec(tick=True))
    assert "Tick" in h


def test_actor_header_tick_disabled_no_tick():
    h = generate_header(_actor_spec(tick=False))
    assert "Tick" not in h


def test_actor_header_pragma_once():
    h = generate_header(_actor_spec())
    assert "#pragma once" in h


# ── generate_header — ActorComponent ─────────────────────────────────────────

def test_component_header_base_class():
    h = generate_header(_component_spec())
    assert "UHealthComponent : public UActorComponent" in h


def test_component_header_blueprint_spawnable():
    h = generate_header(_component_spec())
    assert "BlueprintSpawnableComponent" in h


def test_component_header_property_included():
    h = generate_header(_component_spec())
    assert "MaxHealth" in h
    assert "UPROPERTY" in h


def test_component_header_function_included():
    h = generate_header(_component_spec())
    assert "ApplyDamage" in h
    assert "UFUNCTION" in h


def test_component_header_no_tick_declaration():
    h = generate_header(_component_spec(tick=False))
    assert "TickComponent" not in h


def test_component_header_tick_declaration():
    h = generate_header(_component_spec(tick=True))
    assert "TickComponent" in h


# ── generate_header — DataAsset ───────────────────────────────────────────────

def test_dataasset_header_base_class():
    h = generate_header(_dataasset_spec())
    assert "UWeaponData : public UPrimaryDataAsset" in h


def test_dataasset_header_includes_engine_header():
    h = generate_header(_dataasset_spec())
    assert "Engine/DataAsset.h" in h


def test_dataasset_header_property_included():
    h = generate_header(_dataasset_spec())
    assert "Damage" in h


# ── generate_header — Interface ───────────────────────────────────────────────

def test_interface_header_uinterface_macro():
    h = generate_header(_interface_spec())
    assert "UINTERFACE(" in h


def test_interface_header_u_class():
    h = generate_header(_interface_spec())
    assert "class UInteractable : public UInterface" in h


def test_interface_header_i_class():
    h = generate_header(_interface_spec())
    assert "class MYGAME_API IInteractable" in h


def test_interface_header_function_in_i_class():
    h = generate_header(_interface_spec())
    assert "Interact" in h


# ── generate_source ───────────────────────────────────────────────────────────

def test_actor_source_includes_header():
    cpp = generate_source(_actor_spec())
    assert '#include "MyActor.h"' in cpp


def test_actor_source_constructor():
    cpp = generate_source(_actor_spec())
    assert "AMyActor::AMyActor()" in cpp


def test_actor_source_tick_enabled_sets_can_tick():
    cpp = generate_source(_actor_spec(tick=True))
    assert "bCanEverTick = true" in cpp


def test_actor_source_tick_disabled():
    cpp = generate_source(_actor_spec(tick=False))
    assert "bCanEverTick = false" in cpp


def test_actor_source_begin_play():
    cpp = generate_source(_actor_spec())
    assert "BeginPlay" in cpp
    assert "Super::BeginPlay()" in cpp


def test_component_source_constructor():
    cpp = generate_source(_component_spec())
    assert "UHealthComponent::UHealthComponent()" in cpp


def test_component_source_no_tick_body_when_disabled():
    cpp = generate_source(_component_spec(tick=False))
    assert "TickComponent" not in cpp


def test_interface_source_is_empty_body():
    cpp = generate_source(_interface_spec())
    assert '#include "Interactable.h"' in cpp


def test_dataasset_source_constructor():
    cpp = generate_source(_dataasset_spec())
    assert "UWeaponData::UWeaponData()" in cpp


# ── CLI integration (generate-class --dry-run) ────────────────────────────────

def test_cli_dry_run_does_not_write_files(tmp_path):
    import subprocess, sys, textwrap
    spec_yaml = textwrap.dedent("""\
        class:
          name: TestActor
          type: Actor
          module: MyGame
          tick: false
        properties: []
        functions: []
    """)
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(spec_yaml)
    result = subprocess.run(
        [sys.executable, "-m", "ue_auto",
         "cpp", "generate-class",
         "--spec", str(spec_file),
         "--out", str(tmp_path),
         "--dry-run"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert not (tmp_path / "TestActor.h").exists()
    assert not (tmp_path / "TestActor.cpp").exists()


def test_cli_apply_writes_files(tmp_path):
    import subprocess, sys, textwrap
    spec_yaml = textwrap.dedent("""\
        class:
          name: TestActor
          type: Actor
          module: MyGame
          tick: false
        properties: []
        functions: []
    """)
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(spec_yaml)
    result = subprocess.run(
        [sys.executable, "-m", "ue_auto",
         "cpp", "generate-class",
         "--spec", str(spec_file),
         "--out", str(tmp_path),
         "--apply"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert (tmp_path / "TestActor.h").exists()
    assert (tmp_path / "TestActor.cpp").exists()


def test_cli_apply_header_content(tmp_path):
    import subprocess, sys, textwrap
    spec_yaml = textwrap.dedent("""\
        class:
          name: TestActor
          type: Actor
          module: MyGame
          tick: false
        properties: []
        functions: []
    """)
    spec_file = tmp_path / "spec.yaml"
    spec_file.write_text(spec_yaml)
    subprocess.run(
        [sys.executable, "-m", "ue_auto",
         "cpp", "generate-class",
         "--spec", str(spec_file),
         "--out", str(tmp_path),
         "--apply"],
        capture_output=True,
    )
    content = (tmp_path / "TestActor.h").read_text()
    assert "ATestActor" in content
    assert "AActor" in content
