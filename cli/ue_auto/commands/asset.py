import argparse
import json
import subprocess
from pathlib import Path
from typing import Callable

import yaml

from ue_auto import report as report_mod
from ue_auto import result as result_mod
from ue_auto.runner import find_editor


def load_snapshot(path: str) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Snapshot not found: {path}")
    return json.loads(p.read_text())


def load_policy(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Policy not found: {path}")
    return yaml.safe_load(p.read_text())


def _path_matches(path: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return path == prefix or path.startswith(prefix + "/")
    return path == pattern


def check_prefix(asset: dict, rule: dict) -> dict | None:
    expected = rule.get("prefix")
    if not expected:
        return None
    if not asset["name"].startswith(expected):
        return {
            "type": "PREFIX_VIOLATION",
            "asset": asset["name"],
            "package_path": asset["package_path"],
            "asset_class": asset["asset_class"],
            "expected_prefix": expected,
        }
    return None


def check_path(asset: dict, rule: dict) -> dict | None:
    allowed = rule.get("allowed_paths")
    if not allowed:
        return None
    if any(_path_matches(asset["package_path"], p) for p in allowed):
        return None
    return {
        "type": "PATH_VIOLATION",
        "asset": asset["name"],
        "package_path": asset["package_path"],
        "asset_class": asset["asset_class"],
        "allowed_paths": allowed,
    }


def validate_assets(snapshot: list[dict], policy: dict) -> dict:
    rules_by_class = {r["class"]: r for r in policy.get("rules", [])}
    violations: list[dict] = []

    project_assets = [a for a in snapshot if a.get("package_path", "").startswith("/Game/")]

    for asset in project_assets:
        cls = asset.get("asset_class", "")

        if asset.get("is_redirector"):
            violations.append({
                "type": "REDIRECTOR",
                "asset": asset["name"],
                "package_path": asset["package_path"],
                "asset_class": cls,
            })
            continue

        rule = rules_by_class.get(cls)
        if rule is None:
            continue

        if v := check_prefix(asset, rule):
            violations.append(v)
        if v := check_path(asset, rule):
            violations.append(v)

    return {
        "ok": len(violations) == 0,
        "total": len(project_assets),
        "violation_count": len(violations),
        "violations": violations,
    }


def _write_validation_md(report: dict, path: str) -> None:
    lines = [
        "# Asset Validation Report",
        "",
        f"**Total assets:** {report['total']}  ",
        f"**Violations:** {report['violation_count']}  ",
        "",
    ]
    if report["violations"]:
        lines += ["## Violations", ""]
        for v in report["violations"]:
            lines.append(f"- **{v['type']}** — `{v['asset']}` @ `{v.get('package_path', '')}`")
    else:
        lines.append("All assets passed validation.")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines))


def _cmd_asset_validate(args) -> int:
    snapshot_path = getattr(args, "snapshot", None)
    if not snapshot_path:
        r = result_mod.failure(
            "validate", "MISSING_SNAPSHOT", "--snapshot is required",
            hint="Pass --snapshot path/to/assets.snapshot.json",
        )
        result_mod.write(r, args.result)
        return 1

    try:
        snapshot = load_snapshot(snapshot_path)
    except FileNotFoundError as exc:
        r = result_mod.failure("validate", "SNAPSHOT_NOT_FOUND", str(exc))
        result_mod.write(r, args.result)
        return 1

    policy: dict = {"rules": []}
    policy_path = getattr(args, "policy", None)
    if policy_path:
        try:
            policy = load_policy(policy_path)
        except FileNotFoundError as exc:
            r = result_mod.failure("validate", "POLICY_NOT_FOUND", str(exc))
            result_mod.write(r, args.result)
            return 1

    report = validate_assets(snapshot, policy)
    ok = report["ok"]

    if ok:
        r = result_mod.success("validate", f"All {report['total']} assets passed validation")
    else:
        r = result_mod.failure(
            "validate", "VALIDATION_FAILED",
            f"{report['violation_count']} violations found in {report['total']} assets",
        )
    r["checks"] = report["violations"]
    result_mod.write(r, args.result)

    out_md = getattr(args, "out_md", None)
    if out_md:
        _write_validation_md(report, out_md)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto asset validate  ({report['violation_count']}/{report['total']} violations)")
    return 0 if ok else 1


def _cmd_asset_snapshot(args) -> int:
    project = getattr(args, "project", None)
    if not project:
        r = result_mod.failure(
            "snapshot", "MISSING_PROJECT", "--project is required",
            hint="Pass --project path/to/MyGame.uproject",
        )
        result_mod.write(r, args.result)
        return 1

    editor = find_editor()
    if not editor:
        r = result_mod.failure(
            "snapshot", "EDITOR_NOT_FOUND",
            "UnrealEditor-Cmd not found",
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, args.result)
        return 1

    _out_raw = getattr(args, "out", None) or "Saved/AutomationReports/assets.snapshot.json"
    out = Path(_out_raw).as_posix() if Path(_out_raw).is_absolute() else _out_raw

    cmd = [
        editor,
        str(Path(project).resolve()),
        "-run=AssetSnapshotCommandlet",
        f"-out={out}",
        "-unattended",
        "-nop4",
        "-nosplash",
        "-nullrhi",
    ]
    proc = subprocess.run(cmd)
    ok = proc.returncode == 0

    if ok:
        r = result_mod.success("snapshot", f"Asset snapshot written to {out}")
    else:
        r = result_mod.failure(
            "snapshot", "SNAPSHOT_FAILED",
            f"AssetSnapshotCommandlet failed with exit code {proc.returncode}",
        )
    result_mod.write(r, args.result)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto asset snapshot  (out={out})")
    return 0 if ok else 1


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    snap_p = sub.add_parser("snapshot", help="Capture AssetRegistry snapshot via Commandlet")
    add_common(snap_p)
    snap_p.set_defaults(func=_cmd_asset_snapshot)

    val_p = sub.add_parser("validate", help="Validate asset naming/path against policy")
    add_common(val_p)
    val_p.add_argument("--snapshot", metavar="PATH", help="assets.snapshot.json path")
    val_p.add_argument("--policy", metavar="PATH", help="Policy YAML path")
    val_p.set_defaults(func=_cmd_asset_validate)
