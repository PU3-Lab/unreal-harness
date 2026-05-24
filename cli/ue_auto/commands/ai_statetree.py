import argparse
import json
import subprocess
from pathlib import Path
from typing import Callable

from ue_auto import result as result_mod
from ue_auto.runner import find_editor


# ── snapshot JSON helpers ─────────────────────────────────────────────────────

def load_snapshot(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Snapshot not found: {path}")
    return json.loads(p.read_text(encoding="utf-8"))


# ── validation logic ──────────────────────────────────────────────────────────

def _find_dead_states(states: list[dict]) -> list[dict]:
    """Return violations for states that are never a transition target.

    Root-level states (parent == None, i.e. the tree root) are always reachable.
    Direct children of the root are also considered implicitly reachable when
    the root has no explicit transitions, because the tree starts by activating
    the first child state.
    """
    all_names = {s["name"] for s in states}
    root_names = {s["name"] for s in states if s.get("parent") is None}

    # collect all names that are explicit transition targets
    targeted: set[str] = set()
    for s in states:
        for t in s.get("transitions", []):
            targeted.add(t["target"])

    # Only the first child of each root state is implicitly reachable when root has no
    # explicit transitions — UE StateTree enters the first child on root activation.
    roots_with_transitions = {
        s["name"] for s in states
        if s.get("parent") is None and s.get("transitions")
    }
    root_first_children: set[str] = set()
    seen_root_parents: set[str] = set()
    for s in states:
        parent = s.get("parent")
        if parent in root_names and parent not in roots_with_transitions:
            if parent not in seen_root_parents:
                root_first_children.add(s["name"])
                seen_root_parents.add(parent)

    reachable = root_names | root_first_children | targeted

    violations = []
    for s in states:
        if s["name"] not in reachable:
            violations.append({
                "type": "DEAD_STATE",
                "state": s["name"],
                "message": f"State '{s['name']}' is never reachable via transitions",
            })
    return violations


def _find_missing_targets(states: list[dict]) -> list[dict]:
    all_names = {s["name"] for s in states}
    violations = []
    for s in states:
        for t in s.get("transitions", []):
            target = t.get("target")
            if target and target not in all_names:
                violations.append({
                    "type": "MISSING_TARGET",
                    "state": s["name"],
                    "target": target,
                    "message": f"Transition from '{s['name']}' targets non-existent state '{target}'",
                })
    return violations


def validate_statetree(snapshot: dict) -> dict:
    states = snapshot.get("states", [])
    violations: list[dict] = []
    violations += _find_dead_states(states)
    violations += _find_missing_targets(states)
    return {
        "ok": len(violations) == 0,
        "asset_path": snapshot.get("asset_path", ""),
        "total_states": len(states),
        "violation_count": len(violations),
        "violations": violations,
    }


# ── report generation ─────────────────────────────────────────────────────────

def _build_report_md(snapshot: dict) -> str:
    name = snapshot.get("name", "Unknown")
    asset_path = snapshot.get("asset_path", "")
    states = snapshot.get("states", [])

    total_tasks = sum(len(s.get("tasks", [])) for s in states)
    total_transitions = sum(len(s.get("transitions", [])) for s in states)

    lines = [
        f"# {name} — StateTree 구조 리포트",
        "",
        "## Summary",
        "",
        f"- **Asset:** `{asset_path}`",
        f"- **Total States:** {len(states)}",
        f"- **Total Tasks:** {total_tasks}",
        f"- **Total Transitions:** {total_transitions}",
        "",
        "## States",
        "",
    ]

    for s in states:
        parent = s.get("parent") or "(root)"
        lines.append(f"### {s['name']}")
        lines.append(f"- **Parent:** {parent}")

        tasks = s.get("tasks", [])
        if tasks:
            lines.append("- **Tasks:**")
            for task in tasks:
                lines.append(f"  - `{task}`")
        else:
            lines.append("- **Tasks:** (none)")

        transitions = s.get("transitions", [])
        if transitions:
            lines.append("- **Transitions:**")
            for t in transitions:
                trigger = t.get("trigger", "")
                target = t.get("target", "?")
                lines.append(f"  - → `{target}` (trigger: `{trigger}`)")
        else:
            lines.append("- **Transitions:** (none)")

        lines.append("")

    return "\n".join(lines)


def _write_validation_md(report: dict, path: str) -> None:
    asset = report.get("asset_path", "")
    lines = [
        "# StateTree Validation Report",
        "",
        f"**Asset:** `{asset}`  ",
        f"**Total States:** {report['total_states']}  ",
        f"**Violations:** {report['violation_count']}  ",
        "",
    ]
    if report["violations"]:
        lines += ["## Violations", ""]
        for v in report["violations"]:
            state = v.get("state", "")
            vtype = v["type"]
            msg = v.get("message", "")
            lines.append(f"- **{vtype}** — State `{state}`: {msg}")
        lines.append("")
    else:
        lines.append("All checks passed.")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# ── command implementations ───────────────────────────────────────────────────

def _cmd_statetree_snapshot(args) -> int:
    project = getattr(args, "project", None)
    if not project:
        r = result_mod.failure(
            "statetree-snapshot", "MISSING_PROJECT", "--project is required",
            hint="Pass --project path/to/MyGame.uproject",
        )
        result_mod.write(r, args.result)
        return 1

    asset = getattr(args, "asset", None)
    if not asset:
        r = result_mod.failure(
            "statetree-snapshot", "MISSING_ASSET", "--asset is required",
            hint="Pass --asset /Game/AI/StateTrees/ST_Enemy",
        )
        result_mod.write(r, args.result)
        return 1

    editor = find_editor()
    if not editor:
        r = result_mod.failure(
            "statetree-snapshot", "EDITOR_NOT_FOUND",
            "UnrealEditor-Cmd not found",
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, args.result)
        return 1

    _out_raw = getattr(args, "out", None) or "Saved/AutomationReports/statetree.snapshot.json"
    out = Path(_out_raw).as_posix() if Path(_out_raw).is_absolute() else _out_raw

    cmd = [
        editor,
        str(Path(project).resolve()),
        "-run=StateTreeSnapshotCommandlet",
        f"-asset={asset}",
        f"-out={out}",
        "-unattended",
        "-nop4",
        "-nosplash",
        "-nullrhi",
    ]
    proc = subprocess.run(cmd)
    ok = proc.returncode == 0

    if ok:
        r = result_mod.success("statetree-snapshot", f"StateTree snapshot written to {out}", asset=asset)
    else:
        r = result_mod.failure(
            "statetree-snapshot", "SNAPSHOT_FAILED",
            f"StateTreeSnapshotCommandlet failed with exit code {proc.returncode}",
            asset=asset,
        )
    result_mod.write(r, args.result)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto ai statetree snapshot  (out={out})")
    return 0 if ok else 1


def _cmd_statetree_report(args) -> int:
    snapshot_path = getattr(args, "snapshot", None)
    if not snapshot_path:
        r = result_mod.failure(
            "statetree-report", "MISSING_SNAPSHOT", "--snapshot is required",
            hint="Pass --snapshot path/to/statetree.snapshot.json",
        )
        result_mod.write(r, args.result)
        return 1

    try:
        snapshot = load_snapshot(snapshot_path)
    except FileNotFoundError as exc:
        r = result_mod.failure("statetree-report", "SNAPSHOT_NOT_FOUND", str(exc))
        result_mod.write(r, args.result)
        return 1

    md = _build_report_md(snapshot)

    out_path = getattr(args, "out_md", None) or getattr(args, "out", None)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(md, encoding="utf-8")

    name = snapshot.get("name", "Unknown")
    state_count = len(snapshot.get("states", []))
    r = result_mod.success("statetree-report", f"Report generated for {name} ({state_count} states)")
    result_mod.write(r, args.result)

    status = "PASS"
    print(f"{status}  ue-auto ai statetree report  ({state_count} states)")
    return 0


def _cmd_statetree_validate(args) -> int:
    snapshot_path = getattr(args, "snapshot", None)
    if not snapshot_path:
        r = result_mod.failure(
            "statetree-validate", "MISSING_SNAPSHOT", "--snapshot is required",
            hint="Pass --snapshot path/to/statetree.snapshot.json",
        )
        result_mod.write(r, args.result)
        return 1

    try:
        snapshot = load_snapshot(snapshot_path)
    except FileNotFoundError as exc:
        r = result_mod.failure("statetree-validate", "SNAPSHOT_NOT_FOUND", str(exc))
        result_mod.write(r, args.result)
        return 1

    report = validate_statetree(snapshot)
    ok = report["ok"]

    if ok:
        r = result_mod.success(
            "statetree-validate",
            f"All {report['total_states']} states passed validation",
            asset=report["asset_path"],
        )
    else:
        r = result_mod.failure(
            "statetree-validate", "VALIDATION_FAILED",
            f"{report['violation_count']} violations found",
            asset=report["asset_path"],
        )
    r["checks"] = report["violations"]
    result_mod.write(r, args.result)

    out_json = getattr(args, "out_json", None)
    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        Path(out_json).write_text(
            json.dumps({"ok": ok, "violations": report["violations"]}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    out_md = getattr(args, "out_md", None)
    if out_md:
        _write_validation_md(report, out_md)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto ai statetree validate  ({report['violation_count']}/{report['total_states']} violations)")
    return 0 if ok else 1


# ── ping (kept from Sprint 0) ─────────────────────────────────────────────────

def _cmd_ping(args) -> int:
    import sys
    from ue_auto import report as report_mod
    from ue_auto import runner

    project = getattr(args, "project", None)
    if not project:
        print("error: --project is required for ping", file=sys.stderr)
        r = result_mod.failure("ping", "MISSING_PROJECT", "--project path is required")
        result_mod.write(r, args.result)
        return 1

    result_path = Path(args.project).parent / "Saved/AutomationReports/result.json"
    if result_path.exists():
        result_path.unlink()

    checks: list[dict] = []
    try:
        exit_code = runner.run_commandlet(project, "UEAutoPingCommandlet", timeout=60)
        checks.append({"name": "commandlet_reached", "ok": exit_code == 0})
    except runner.RunnerError as e:
        print(f"error: {e}", file=sys.stderr)
        r = result_mod.failure(
            "ping", "EDITOR_NOT_FOUND", str(e),
            hint="Set UE_EDITOR_CMD env var to the UnrealEditor-Cmd path.",
        )
        result_mod.write(r, args.result)
        return 1

    commandlet_ok = False
    if result_path.exists():
        with open(result_path, encoding="utf-8") as f:
            data = json.load(f)
        commandlet_ok = bool(data.get("ok"))
    checks.append({"name": "result_json_written", "ok": commandlet_ok})

    overall_ok = all(c["ok"] for c in checks)
    if overall_ok:
        r = result_mod.success("ping", "pong", checks=checks)
    else:
        r = result_mod.failure("ping", "PING_FAILED", "One or more checks failed",
                               hint="Check UE Editor logs in Saved/Logs/.")
        r["checks"] = checks
    result_mod.write(r, args.result)

    status = "PASS" if overall_ok else "FAIL"
    print(f"{status}  ue-auto ai statetree ping")
    return 0 if overall_ok else 1


# ── stub for unimplemented commands ───────────────────────────────────────────

def _make_stub(verb: str):
    import sys

    def _stub(args):
        print(f"ue-auto ai statetree {verb}: not yet implemented", file=sys.stderr)
        r = result_mod.failure(verb, "NOT_IMPLEMENTED", f"{verb} is not yet implemented")
        result_mod.write(r, args.result)
        return 1
    return _stub


# ── argparse registration ─────────────────────────────────────────────────────

def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    # ping
    ping_p = sub.add_parser("ping", help="Verify CLI→Editor pipeline end-to-end")
    add_common(ping_p)
    ping_p.set_defaults(func=_cmd_ping)

    # snapshot
    snap_p = sub.add_parser("snapshot", help="Export StateTree structure to JSON")
    add_common(snap_p)
    snap_p.add_argument("--asset", metavar="PATH", help="UE asset path (e.g. /Game/AI/ST_Enemy)")
    snap_p.set_defaults(func=_cmd_statetree_snapshot)

    # report
    rep_p = sub.add_parser("report", help="Generate Markdown report from snapshot")
    add_common(rep_p)
    rep_p.add_argument("--snapshot", metavar="PATH", help="statetree.snapshot.json path")
    rep_p.set_defaults(func=_cmd_statetree_report)

    # validate
    val_p = sub.add_parser("validate", help="Validate StateTree structure (Dead State, Missing Target)")
    add_common(val_p)
    val_p.add_argument("--snapshot", metavar="PATH", help="statetree.snapshot.json path")
    val_p.set_defaults(func=_cmd_statetree_validate)

    # stubs for Sprint 4+
    for verb in ("create", "add-state", "add-task", "add-transition", "add-condition", "compile"):
        p = sub.add_parser(verb, help=f"[stub] {verb}")
        add_common(p)
        p.set_defaults(func=_make_stub(verb))
