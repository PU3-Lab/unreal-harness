import json
import textwrap
import pytest
from pathlib import Path

from ue_auto.commands.asset import (
    load_snapshot,
    load_policy,
    check_prefix,
    check_path,
    validate_assets,
)


POLICY_YAML = textwrap.dedent("""\
    rules:
      - class: Blueprint
        prefix: BP_
        allowed_paths:
          - /Game/Characters/**
          - /Game/Systems/**
""")


# ── load_snapshot ─────────────────────────────────────────────────────────────

def test_load_snapshot_returns_list(tmp_path):
    data = [{"name": "BP_Hero", "package_path": "/Game/Characters", "asset_class": "Blueprint", "is_redirector": False}]
    f = tmp_path / "snap.json"
    f.write_text(json.dumps(data))
    assert load_snapshot(str(f)) == data


def test_load_snapshot_empty_list(tmp_path):
    f = tmp_path / "snap.json"
    f.write_text("[]")
    assert load_snapshot(str(f)) == []


def test_load_snapshot_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_snapshot(str(tmp_path / "missing.json"))


# ── load_policy ───────────────────────────────────────────────────────────────

def test_load_policy_returns_rules(tmp_path):
    f = tmp_path / "policy.yaml"
    f.write_text(POLICY_YAML)
    policy = load_policy(str(f))
    assert len(policy["rules"]) == 1
    rule = policy["rules"][0]
    assert rule["class"] == "Blueprint"
    assert rule["prefix"] == "BP_"
    assert "/Game/Characters/**" in rule["allowed_paths"]


def test_load_policy_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_policy(str(tmp_path / "missing.yaml"))


# ── check_prefix ──────────────────────────────────────────────────────────────

def test_check_prefix_pass():
    asset = {"name": "BP_Hero", "asset_class": "Blueprint", "package_path": "/Game/Characters"}
    rule = {"class": "Blueprint", "prefix": "BP_", "allowed_paths": ["/Game/**"]}
    assert check_prefix(asset, rule) is None


def test_check_prefix_fail_returns_violation():
    asset = {"name": "Hero", "asset_class": "Blueprint", "package_path": "/Game/Characters"}
    rule = {"class": "Blueprint", "prefix": "BP_", "allowed_paths": ["/Game/**"]}
    v = check_prefix(asset, rule)
    assert v is not None
    assert v["type"] == "PREFIX_VIOLATION"
    assert v["asset"] == "Hero"
    assert "BP_" in v["expected_prefix"]


def test_check_prefix_rule_without_prefix_skips():
    asset = {"name": "Hero", "asset_class": "Blueprint", "package_path": "/Game"}
    rule = {"class": "Blueprint", "allowed_paths": ["/Game/**"]}
    assert check_prefix(asset, rule) is None


# ── check_path ────────────────────────────────────────────────────────────────

def test_check_path_pass_double_star():
    asset = {"name": "BP_Hero", "asset_class": "Blueprint", "package_path": "/Game/Characters/Hero/Blueprints"}
    rule = {"class": "Blueprint", "prefix": "BP_", "allowed_paths": ["/Game/Characters/**"]}
    assert check_path(asset, rule) is None


def test_check_path_pass_prefix_exact():
    asset = {"name": "BP_Hero", "asset_class": "Blueprint", "package_path": "/Game/Characters"}
    rule = {"class": "Blueprint", "prefix": "BP_", "allowed_paths": ["/Game/Characters/**"]}
    assert check_path(asset, rule) is None


def test_check_path_pass_second_pattern():
    asset = {"name": "BP_Sys", "asset_class": "Blueprint", "package_path": "/Game/Systems/Core"}
    rule = {"class": "Blueprint", "prefix": "BP_", "allowed_paths": ["/Game/Characters/**", "/Game/Systems/**"]}
    assert check_path(asset, rule) is None


def test_check_path_fail_returns_violation():
    asset = {"name": "BP_Hero", "asset_class": "Blueprint", "package_path": "/Game/WrongPlace"}
    rule = {"class": "Blueprint", "prefix": "BP_", "allowed_paths": ["/Game/Characters/**"]}
    v = check_path(asset, rule)
    assert v is not None
    assert v["type"] == "PATH_VIOLATION"
    assert v["asset"] == "BP_Hero"


def test_check_path_rule_without_allowed_paths_skips():
    asset = {"name": "BP_Hero", "asset_class": "Blueprint", "package_path": "/Game/Anywhere"}
    rule = {"class": "Blueprint", "prefix": "BP_"}
    assert check_path(asset, rule) is None


# ── validate_assets ───────────────────────────────────────────────────────────

def _asset(name, cls, path, is_redirector=False):
    return {"name": name, "asset_class": cls, "package_path": path, "is_redirector": is_redirector}


def _bp_rule(**overrides):
    r = {"class": "Blueprint", "prefix": "BP_", "allowed_paths": ["/Game/**"]}
    r.update(overrides)
    return r


def test_validate_assets_all_clean():
    snap = [_asset("BP_Hero", "Blueprint", "/Game/Characters")]
    pol = {"rules": [_bp_rule()]}
    r = validate_assets(snap, pol)
    assert r["ok"] is True
    assert r["violations"] == []
    assert r["total"] == 1


def test_validate_assets_prefix_violation():
    snap = [_asset("Hero", "Blueprint", "/Game/Characters")]
    pol = {"rules": [_bp_rule()]}
    r = validate_assets(snap, pol)
    assert r["ok"] is False
    assert any(v["type"] == "PREFIX_VIOLATION" for v in r["violations"])


def test_validate_assets_path_violation():
    snap = [_asset("BP_Hero", "Blueprint", "/Game/Wrong")]
    pol = {"rules": [_bp_rule(allowed_paths=["/Game/Characters/**"])]}
    r = validate_assets(snap, pol)
    assert r["ok"] is False
    assert any(v["type"] == "PATH_VIOLATION" for v in r["violations"])


def test_validate_assets_redirector_flagged():
    snap = [_asset("BP_Hero", "Blueprint", "/Game/Characters", is_redirector=True)]
    pol = {"rules": [_bp_rule()]}
    r = validate_assets(snap, pol)
    assert r["ok"] is False
    assert any(v["type"] == "REDIRECTOR" for v in r["violations"])


def test_validate_assets_no_rule_for_class_skips():
    snap = [_asset("SM_Cube", "StaticMesh", "/Game/Meshes")]
    pol = {"rules": [_bp_rule()]}
    r = validate_assets(snap, pol)
    assert r["ok"] is True
    assert r["violations"] == []


def test_validate_assets_counts_multiple_violations():
    snap = [
        _asset("BP_Hero", "Blueprint", "/Game/Characters"),   # clean
        _asset("Hero2",   "Blueprint", "/Game/Characters"),   # prefix violation
        _asset("BP_Bad",  "Blueprint", "/Game/Wrong"),        # path violation
    ]
    pol = {"rules": [_bp_rule(allowed_paths=["/Game/Characters/**"])]}
    r = validate_assets(snap, pol)
    assert r["ok"] is False
    assert r["total"] == 3
    assert r["violation_count"] >= 2


def test_validate_assets_empty_snapshot():
    r = validate_assets([], {"rules": [_bp_rule()]})
    assert r["ok"] is True
    assert r["total"] == 0
