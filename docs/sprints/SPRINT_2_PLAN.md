# Sprint 2 Plan: Asset Naming / Path Pipeline

## Goal

`ue-auto asset validate` (pure Python) + `ue-auto asset snapshot` (UE Commandlet stub)

---

## Phases

### Phase 1 — Tests for `asset validate` (TDD RED)
File: `cli/tests/test_asset_validate.py`

Functions under test:
- `load_snapshot(path)` → `list[dict]`
- `load_policy(path)` → `dict`
- `check_prefix(asset, rule)` → `dict | None`
- `check_path(asset, rule)` → `dict | None`
- `validate_assets(snapshot, policy)` → `dict`

### Phase 2 — Implement `asset validate` (TDD GREEN)
File: `cli/ue_auto/commands/asset.py`

CLI args added to `validate` subparser:
- `--snapshot PATH` (required at runtime)
- `--policy PATH` (optional, unified YAML)
- `--out-md PATH` (optional markdown report)

Policy YAML format:
```yaml
rules:
  - class: Blueprint
    prefix: BP_
    allowed_paths:
      - /Game/Characters/**
      - /Game/Systems/**
```

Violation types: `PREFIX_VIOLATION`, `PATH_VIOLATION`, `REDIRECTOR`

### Phase 3 — Tests + Implementation for `asset snapshot` (TDD)
File: `cli/tests/test_asset_snapshot.py`

Mocks `subprocess.run` + `find_editor`.  
Verifies commandlet invocation: `-run=AssetSnapshotCommandlet -out=<out>`.

### Phase 4 — UE Plugin: AssetSnapshotCommandlet
Files:
- `plugin/UEAutomationBridge/Source/.../Public/Commandlets/AssetSnapshotCommandlet.h`
- `plugin/UEAutomationBridge/Source/.../Private/Commandlets/AssetSnapshotCommandlet.cpp`

Writes `assets.snapshot.json` with fields:
`name`, `package_path`, `asset_class`, `is_redirector`

### Phase 5 — Sample policy YAML files
- `docs/asset_rules/assets.naming_policy.yaml`

---

## Outputs

| File | Description |
|---|---|
| `docs/asset_rules/assets.naming_policy.yaml` | Sample naming/path policy |
| `Saved/AutomationReports/assets.snapshot.json` | AssetRegistry snapshot (from Commandlet) |
| `Saved/AutomationReports/assets.validation.md` | Human-readable validation report |
| `Saved/AutomationReports/result.json` | Machine-readable result |

---

## Success Criteria

- All `test_asset_validate.py` tests pass
- All `test_asset_snapshot.py` tests pass
- `ue-auto asset validate --snapshot snap.json --policy policy.yaml` exits 0 on clean input, 1 on violations
- `ue-auto asset snapshot` calls AssetSnapshotCommandlet with correct args (mocked)
- Full test suite stays green (`pytest` no regressions)
