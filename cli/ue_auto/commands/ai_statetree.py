import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from ue_auto import result as result_mod
from ue_auto.runner import find_editor


# ── snapshot JSON helpers ─────────────────────────────────────────────────────

def load_snapshot(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Snapshot not found: {path}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in snapshot '{path}': {e}") from e


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


def _find_no_exit_transitions(states: list[dict]) -> list[dict]:
    """Flag leaf states (no children) that have no outgoing transitions."""
    container_names = {s.get("parent") for s in states if s.get("parent") is not None}
    violations = []
    for s in states:
        if s.get("parent") is None:
            continue
        if s["name"] in container_names:
            continue
        if not s.get("transitions"):
            violations.append({
                "type": "NO_EXIT_TRANSITION",
                "state": s["name"],
                "message": f"Leaf state '{s['name']}' has no exit transitions (tree will be stuck here)",
            })
    return violations


def _find_invalid_evaluators(snapshot: dict) -> list[dict]:
    """Flag evaluators whose class is 'None' or empty."""
    violations = []
    for i, ev in enumerate(snapshot.get("evaluators", [])):
        cls = ev.get("class", "")
        if not cls or cls == "None":
            violations.append({
                "type": "INVALID_EVALUATOR",
                "state": f"<evaluator[{i}]>",
                "message": f"Evaluator at index {i} has invalid class '{cls}'",
            })
    return violations


def _find_duplicate_states(states: list[dict]) -> list[dict]:
    """Flag state names that appear more than once."""
    counts: dict[str, int] = {}
    for s in states:
        name = s["name"]
        counts[name] = counts.get(name, 0) + 1
    return [
        {
            "type": "DUPLICATE_STATE",
            "state": name,
            "message": f"State '{name}' appears {count} times",
        }
        for name, count in counts.items()
        if count > 1
    ]


def _find_spec_mismatches(snapshot: dict, spec: dict) -> list[dict]:
    """Compare expected state names from spec with actual snapshot states."""
    expected = {s["name"] for s in spec.get("states", [])}
    actual = {s["name"] for s in snapshot.get("states", [])}
    violations = []
    for name in sorted(expected - actual):
        violations.append({
            "type": "SPEC_MISMATCH",
            "state": name,
            "message": f"State '{name}' expected by spec but not found in snapshot",
        })
    for name in sorted(actual - expected):
        violations.append({
            "type": "SPEC_MISMATCH",
            "state": name,
            "message": f"State '{name}' found in snapshot but not expected by spec",
        })
    return violations


def validate_statetree(snapshot: dict, spec: dict | None = None) -> dict:
    states = snapshot.get("states", [])
    violations: list[dict] = []
    violations += _find_dead_states(states)
    violations += _find_missing_targets(states)
    violations += _find_no_exit_transitions(states)
    violations += _find_invalid_evaluators(snapshot)
    violations += _find_duplicate_states(states)
    if spec is not None:
        violations += _find_spec_mismatches(snapshot, spec)
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

    total_tasks = sum(len(s.get("tasks") or []) for s in states)
    total_transitions = sum(len(s.get("transitions") or []) for s in states)

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

        tasks = s.get("tasks") or []
        if tasks:
            lines.append("- **Tasks:**")
            for task in tasks:
                lines.append(f"  - `{task}`")
        else:
            lines.append("- **Tasks:** (none)")

        transitions = s.get("transitions") or []
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

def _cmd_statetree_snapshot(args: Any) -> int:
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
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        r = result_mod.failure(
            "statetree-snapshot", "EDITOR_NOT_FOUND", str(exc),
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, args.result)
        return 1

    ok = proc.returncode == 0

    if ok:
        r = result_mod.success("statetree-snapshot", f"StateTree snapshot written to {out}", asset=asset)
    else:
        if proc.stderr:
            print(proc.stderr[:500], file=sys.stderr)
        r = result_mod.failure(
            "statetree-snapshot", "SNAPSHOT_FAILED",
            f"StateTreeSnapshotCommandlet failed with exit code {proc.returncode}",
            asset=asset,
        )
    result_mod.write(r, args.result)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto ai statetree snapshot  (out={out})")
    return 0 if ok else 1


def _cmd_statetree_report(args: Any) -> int:
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
    except (FileNotFoundError, ValueError) as exc:
        code = "SNAPSHOT_NOT_FOUND" if isinstance(exc, FileNotFoundError) else "SNAPSHOT_PARSE_ERROR"
        r = result_mod.failure("statetree-report", code, str(exc))
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


def _cmd_statetree_validate(args: Any) -> int:
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
    except (FileNotFoundError, ValueError) as exc:
        code = "SNAPSHOT_NOT_FOUND" if isinstance(exc, FileNotFoundError) else "SNAPSHOT_PARSE_ERROR"
        r = result_mod.failure("statetree-validate", code, str(exc))
        result_mod.write(r, args.result)
        return 1

    spec: dict | None = None
    spec_path = getattr(args, "spec", None)
    if spec_path:
        import yaml as _yaml
        p = Path(spec_path)
        if not p.exists():
            r = result_mod.failure(
                "statetree-validate", "SPEC_NOT_FOUND", f"Spec not found: {spec_path}",
            )
            result_mod.write(r, args.result)
            return 1
        spec = _yaml.safe_load(p.read_text(encoding="utf-8"))

    report = validate_statetree(snapshot, spec=spec)
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

def _cmd_ping(args: Any) -> int:
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


# ── statetree create ─────────────────────────────────────────────────────────

def parse_create_spec(path: str) -> dict:
    from pathlib import Path as _Path
    import yaml as _yaml

    p = _Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Spec not found: {path}")
    data = _yaml.safe_load(p.read_text())
    if not isinstance(data, dict) or "character" not in data:
        raise ValueError("Spec must have a top-level 'character' key")
    if "statetree" not in data:
        raise ValueError("Spec must have a top-level 'statetree' key")
    data["character"].setdefault("parent_class", "Character")
    return data


def generate_create_script(spec: dict, result_json_path: str = "") -> str:
    char = spec["character"]
    st = spec["statetree"]
    char_name = char["name"]
    char_path = char["content_path"]
    parent_class = char["parent_class"]
    st_name = st["name"]
    st_path = st["content_path"]
    result_out = result_json_path or ""

    return f'''\
import unreal
import json

def _create_and_validate():
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    checks = []
    assets = []

    # Ensure content browser directories exist
    for _dir in ["{st_path}", "{char_path}"]:
        unreal.EditorAssetLibrary.make_directory(_dir)

    # 1. Create StateTree asset (ghost files cleaned up before UE launch)
    st_asset = asset_tools.create_asset(
        asset_name="{st_name}",
        package_path="{st_path}",
        asset_class=unreal.StateTree,
        factory=None,
    )
    if st_asset is None:
        st_asset = unreal.EditorAssetLibrary.load_asset("{st_path}/{st_name}")
    checks.append({{"name": "statetree_created", "ok": st_asset is not None}})

    # 2. Create Blueprint character
    bp_factory = unreal.BlueprintFactory()
    bp_factory.set_editor_property("parent_class", unreal.{parent_class})
    bp_char = asset_tools.create_asset(
        asset_name="{char_name}",
        package_path="{char_path}",
        asset_class=unreal.Blueprint,
        factory=bp_factory,
    )
    if bp_char is None:
        bp_char = unreal.EditorAssetLibrary.load_asset("{char_path}/{char_name}")
    checks.append({{"name": "blueprint_created", "ok": bp_char is not None}})

    if st_asset is None or bp_char is None:
        _write_result(checks, assets, "{result_out}")
        return

    # 3. Add StateTreeComponent
    # SubobjectDataSubsystem is an EngineSubsystem, not an EditorSubsystem
    sds = unreal.get_engine_subsystem(unreal.SubobjectDataSubsystem)
    root_handle = sds.k2_gather_subobject_data_for_blueprint(bp_char)[0]
    new_handle, fail_reason = sds.add_new_subobject(
        params=unreal.AddNewSubobjectParams(
            parent_handle=root_handle,
            new_class=unreal.StateTreeComponent,
            blueprint_context=bp_char,
        )
    )
    comp_ok = str(fail_reason) == ""
    checks.append({{"name": "component_added", "ok": comp_ok}})

    if comp_ok:
        sds.rename_subobject(handle=new_handle, new_name="StateTreeComponent")

        # 4. Assign StateTree to component
        # state_tree_ref is FStateTreeReference (a struct), not UStateTree directly
        sub_data = sds.k2_find_subobject_data_from_handle(new_handle)
        comp_tmpl = unreal.SubobjectDataBlueprintFunctionLibrary.get_object(sub_data)
        st_ref = unreal.StateTreeReference()
        st_ref.set_editor_property("state_tree", st_asset)
        comp_tmpl.set_editor_property("state_tree_ref", st_ref)
        assigned_ref = comp_tmpl.get_editor_property("state_tree_ref")
        assigned = assigned_ref.get_editor_property("state_tree") if assigned_ref else None
        checks.append({{"name": "statetree_assigned", "ok": assigned is not None}})
    else:
        checks.append({{"name": "statetree_assigned", "ok": False}})

    # 5. Compile Blueprint
    unreal.BlueprintEditorLibrary.compile_blueprint(bp_char)

    # 6. Save and validate assets exist on disk
    unreal.EditorAssetLibrary.save_asset(st_asset.get_path_name())
    unreal.EditorAssetLibrary.save_asset(bp_char.get_path_name())
    st_saved = unreal.EditorAssetLibrary.does_asset_exist(st_asset.get_path_name())
    bp_saved = unreal.EditorAssetLibrary.does_asset_exist(bp_char.get_path_name())
    checks.append({{"name": "assets_saved", "ok": st_saved and bp_saved}})

    if st_saved:
        assets.append(st_asset.get_path_name())
    if bp_saved:
        assets.append(bp_char.get_path_name())

    print(f"CREATED statetree={{st_asset.get_path_name()}}")
    print(f"CREATED character={{bp_char.get_path_name()}}")
    _write_result(checks, assets, "{result_out}")


def _write_result(checks, assets, path):
    ok = all(c["ok"] for c in checks)
    result = {{"ok": ok, "checks": checks, "assets": assets}}
    if path:
        import pathlib
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    print(f"RESULT ok={{ok}} checks={{len(checks)}}")


try:
    _create_and_validate()
except Exception as _exc:
    import traceback
    _tb = traceback.format_exc()
    print(f"UNHANDLED EXCEPTION: {{_exc}}")
    print(_tb)
    _write_result(
        [{{"name": "unhandled_exception", "ok": False, "detail": str(_exc)}}],
        [],
        "{result_out}",
    )
'''


def _cmd_statetree_create(args: Any) -> int:
    spec_path = getattr(args, "spec", None)
    out_dir = getattr(args, "out", None) or "."
    project = getattr(args, "project", None)
    dry_run = getattr(args, "dry_run", True)
    if getattr(args, "apply", False):
        dry_run = False

    if not spec_path:
        r = result_mod.failure(
            "statetree-create", "MISSING_SPEC", "--spec is required",
            hint="Pass --spec path/to/create.spec.yaml",
        )
        result_mod.write(r, getattr(args, "result", None))
        return 1

    try:
        spec = parse_create_spec(spec_path)
    except (FileNotFoundError, ValueError) as exc:
        r = result_mod.failure("statetree-create", "SPEC_ERROR", str(exc))
        result_mod.write(r, getattr(args, "result", None))
        return 1

    char_name = spec["character"]["name"]
    st_name = spec["statetree"]["name"]
    out = Path(out_dir)
    script_path = out / "statetree_create.py"
    result_json_path = out / "statetree_create.result.json"

    script = generate_create_script(spec, result_json_path=str(result_json_path))

    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"{mode}  ue-auto ai statetree create  ({char_name} + {st_name})")

    if dry_run:
        r = result_mod.success("statetree-create", f"Would create {char_name} + {st_name}")
        r["dry_run"] = True
        result_mod.write(r, getattr(args, "result", None))
        return 0

    # Write script
    out.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script, encoding="utf-8")

    # Without project: script written, UE execution skipped
    if not project:
        r = result_mod.success(
            "statetree-create",
            f"Script generated: {script_path} (pass --project to execute via UE)",
        )
        r["script"] = str(script_path)
        result_mod.write(r, getattr(args, "result", None))
        return 0

    # Find UE editor
    editor = find_editor()
    if not editor:
        r = result_mod.failure(
            "statetree-create", "EDITOR_NOT_FOUND",
            "UnrealEditor-Cmd not found",
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, getattr(args, "result", None))
        return 1

    # Remove ghost .uasset files before launching UE — ghost packages block
    # create_asset even when does_asset_exist returns False.
    content_dir = Path(project).parent / "Content"
    for asset_key, asset_content_path in [
        ("statetree", spec["statetree"]["content_path"]),
        ("character", spec["character"]["content_path"]),
    ]:
        asset_name = spec[asset_key]["name"]
        rel = asset_content_path.replace("/Game/", "", 1).lstrip("/")
        ghost = content_dir / rel / (asset_name + ".uasset")
        if ghost.exists():
            ghost.unlink()

    # Execute via UE
    cmd = [
        editor,
        str(Path(project).resolve()),
        f"-ExecutePythonScript={script_path}",
        "-unattended",
        "-nop4",
        "-nosplash",
        "-nullrhi",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0:
        if proc.stderr:
            print(proc.stderr[:500], file=sys.stderr)
        r = result_mod.failure(
            "statetree-create", "UE_EXECUTION_FAILED",
            f"UnrealEditor-Cmd exited with code {proc.returncode}",
        )
        result_mod.write(r, getattr(args, "result", None))
        return 1

    # Read result JSON written by the script
    ok = False
    checks: list[dict] = []
    assets: list[str] = []
    if result_json_path.exists():
        try:
            data = json.loads(result_json_path.read_text(encoding="utf-8"))
            ok = bool(data.get("ok", False))
            checks = data.get("checks", [])
            assets = data.get("assets", [])
        except (json.JSONDecodeError, OSError):
            ok = False

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto ai statetree create  ({len(assets)} assets created)")

    if ok:
        r = result_mod.success(
            "statetree-create",
            f"Created {char_name} + {st_name} ({len(assets)} assets)",
        )
    else:
        failed = [c["name"] for c in checks if not c.get("ok")]
        r = result_mod.failure(
            "statetree-create", "CREATE_VALIDATION_FAILED",
            f"Validation failed: {', '.join(failed) if failed else 'result.json missing'}",
        )
    r["checks"] = checks
    r["assets"] = assets
    result_mod.write(r, getattr(args, "result", None))
    return 0 if ok else 1


# ── wire command ─────────────────────────────────────────────────────────────

def parse_wire_spec(path: str) -> dict:
    import yaml as _yaml

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Spec not found: {path}")
    data = _yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "statetree" not in data:
        raise ValueError("Spec must have a top-level 'statetree' key")
    if "asset" not in data["statetree"]:
        raise ValueError("Spec must have 'statetree.asset' key")
    return data


def _cmd_statetree_wire(args: Any) -> int:
    project = getattr(args, "project", None)
    asset = getattr(args, "asset", None)
    spec_path = getattr(args, "spec", None)
    dry_run = getattr(args, "dry_run", False)

    if not project:
        r = result_mod.failure(
            "statetree-wire", "MISSING_PROJECT", "--project is required",
            hint="Pass --project path/to/MyGame.uproject",
        )
        result_mod.write(r, args.result)
        return 1

    wire_spec: dict | None = None
    if spec_path:
        try:
            wire_spec = parse_wire_spec(spec_path)
        except FileNotFoundError as exc:
            r = result_mod.failure("statetree-wire", "SPEC_NOT_FOUND", str(exc))
            result_mod.write(r, args.result)
            return 1
        except ValueError as exc:
            r = result_mod.failure("statetree-wire", "SPEC_ERROR", str(exc))
            result_mod.write(r, args.result)
            return 1
        if not asset:
            asset = wire_spec["statetree"]["asset"]

    if not asset:
        r = result_mod.failure(
            "statetree-wire", "MISSING_ASSET", "--asset is required",
            hint="Pass --asset /Game/AI/ST_EnemyAI or provide a spec with statetree.asset",
        )
        result_mod.write(r, args.result)
        return 1

    if dry_run:
        r = result_mod.success("statetree-wire", f"[dry-run] Would wire {asset}", asset=asset)
        r["dry_run"] = True
        result_mod.write(r, args.result)
        status = "DRY-RUN"
        print(f"{status}  ue-auto ai statetree wire  (asset={asset})")
        return 0

    editor = find_editor()
    if not editor:
        r = result_mod.failure(
            "statetree-wire", "EDITOR_NOT_FOUND",
            "UnrealEditor-Cmd not found",
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, args.result)
        return 1

    _out_raw = getattr(args, "out", None) or "Saved/AutomationReports/statetree.wire.result.json"
    out = Path(_out_raw).as_posix() if Path(_out_raw).is_absolute() else _out_raw

    cmd = [
        editor,
        str(Path(project).resolve()),
        "-run=StateTreeWireCommandlet",
        f"-asset={asset}",
        f"-out={out}",
        "-unattended",
        "-nop4",
        "-nosplash",
        "-nullrhi",
    ]

    if wire_spec is not None:
        spec_json_path = Path(out).parent / "statetree.wire.spec.json"
        spec_json_path.parent.mkdir(parents=True, exist_ok=True)
        spec_json_path.write_text(json.dumps(wire_spec, ensure_ascii=False), encoding="utf-8")
        cmd.append(f"-spec={spec_json_path.as_posix()}")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        r = result_mod.failure(
            "statetree-wire", "EDITOR_NOT_FOUND", str(exc),
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, args.result)
        return 1

    ok = proc.returncode == 0

    result_data: dict = {}
    result_path = Path(out) if Path(out).is_absolute() else Path(project).parent / out
    if result_path.exists():
        try:
            result_data = json.loads(result_path.read_text(encoding="utf-8"))
            ok = ok and bool(result_data.get("ok", False))
        except (json.JSONDecodeError, OSError):
            pass

    if ok:
        msg = result_data.get("message", f"StateTree wired: {asset}")
        r = result_mod.success("statetree-wire", msg, asset=asset)
    else:
        if proc.stderr:
            print(proc.stderr[:500], file=sys.stderr)
        error_code = result_data.get("error_code", "WIRE_FAILED")
        error_msg = result_data.get("message") or f"StateTreeWireCommandlet failed (exit {proc.returncode})"
        r = result_mod.failure("statetree-wire", error_code, error_msg, asset=asset)
    result_mod.write(r, args.result)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto ai statetree wire  (asset={asset})")
    return 0 if ok else 1


# ── spec-file helpers ─────────────────────────────────────────────────────────

def _load_spec_for_edit(spec_path: str) -> dict:
    import yaml as _yaml

    p = Path(spec_path)
    if not p.exists():
        raise FileNotFoundError(f"Spec not found: {spec_path}")
    data = _yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "statetree" not in data:
        raise ValueError("Spec must have a top-level 'statetree' key")
    return data


def _save_spec_yaml(spec_path: str, data: dict) -> None:
    import yaml as _yaml

    Path(spec_path).write_text(
        _yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


def _find_state(states: list[dict], name: str) -> dict | None:
    return next((s for s in states if s.get("name") == name), None)


# ── add-state ─────────────────────────────────────────────────────────────────

def _cmd_statetree_add_state(args: Any) -> int:
    spec_path = getattr(args, "spec", None)
    name = getattr(args, "name", None)

    if not spec_path:
        r = result_mod.failure("statetree-add-state", "MISSING_SPEC", "--spec is required")
        result_mod.write(r, args.result)
        return 1

    if not name:
        r = result_mod.failure("statetree-add-state", "MISSING_NAME", "--name is required")
        result_mod.write(r, args.result)
        return 1

    try:
        data = _load_spec_for_edit(spec_path)
    except FileNotFoundError as exc:
        r = result_mod.failure("statetree-add-state", "SPEC_NOT_FOUND", str(exc))
        result_mod.write(r, args.result)
        return 1
    except ValueError as exc:
        r = result_mod.failure("statetree-add-state", "SPEC_ERROR", str(exc))
        result_mod.write(r, args.result)
        return 1

    st = data["statetree"]
    states: list[dict] = st.setdefault("states", [])

    if _find_state(states, name):
        r = result_mod.failure(
            "statetree-add-state", "DUPLICATE_STATE", f"State '{name}' already exists"
        )
        result_mod.write(r, args.result)
        return 1

    if getattr(args, "dry_run", False):
        r = result_mod.success(
            "statetree-add-state", f"[dry-run] Would add state '{name}' to {spec_path}"
        )
        r["dry_run"] = True
        result_mod.write(r, args.result)
        print(f"DRY-RUN  ue-auto ai statetree add-state  (name={name})")
        return 0

    new_state: dict = {"name": name}
    if parent := getattr(args, "parent", None):
        new_state["parent"] = parent
    states.append(new_state)
    _save_spec_yaml(spec_path, data)

    r = result_mod.success("statetree-add-state", f"Added state '{name}' to {spec_path}")
    result_mod.write(r, args.result)
    print(f"PASS  ue-auto ai statetree add-state  (name={name})")
    return 0


# ── add-task ──────────────────────────────────────────────────────────────────

def _cmd_statetree_add_task(args: Any) -> int:
    spec_path = getattr(args, "spec", None)
    state_name = getattr(args, "state", None)
    cls = getattr(args, "cls", None)
    params_str = getattr(args, "params", None)

    if not spec_path:
        r = result_mod.failure("statetree-add-task", "MISSING_SPEC", "--spec is required")
        result_mod.write(r, args.result)
        return 1

    if not cls:
        r = result_mod.failure("statetree-add-task", "MISSING_CLASS", "--class is required")
        result_mod.write(r, args.result)
        return 1

    try:
        data = _load_spec_for_edit(spec_path)
    except FileNotFoundError as exc:
        r = result_mod.failure("statetree-add-task", "SPEC_NOT_FOUND", str(exc))
        result_mod.write(r, args.result)
        return 1
    except ValueError as exc:
        r = result_mod.failure("statetree-add-task", "SPEC_ERROR", str(exc))
        result_mod.write(r, args.result)
        return 1

    states: list[dict] = data["statetree"].setdefault("states", [])
    state = _find_state(states, state_name)
    if not state:
        r = result_mod.failure(
            "statetree-add-task", "STATE_NOT_FOUND", f"State '{state_name}' not found in spec"
        )
        result_mod.write(r, args.result)
        return 1

    params: dict = {}
    if params_str:
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError as exc:
            r = result_mod.failure("statetree-add-task", "INVALID_PARAMS", str(exc))
            result_mod.write(r, args.result)
            return 1

    task_entry: dict = {"class": cls, **params}
    state.setdefault("tasks", []).append(task_entry)
    _save_spec_yaml(spec_path, data)

    r = result_mod.success(
        "statetree-add-task", f"Added task '{cls}' to state '{state_name}' in {spec_path}"
    )
    result_mod.write(r, args.result)
    print(f"PASS  ue-auto ai statetree add-task  (state={state_name}, class={cls})")
    return 0


# ── add-transition ────────────────────────────────────────────────────────────

def _cmd_statetree_add_transition(args: Any) -> int:
    spec_path = getattr(args, "spec", None)
    state_name = getattr(args, "state", None)
    trigger = getattr(args, "trigger", None)
    target = getattr(args, "target", None)

    if not spec_path:
        r = result_mod.failure("statetree-add-transition", "MISSING_SPEC", "--spec is required")
        result_mod.write(r, args.result)
        return 1

    if not state_name:
        r = result_mod.failure("statetree-add-transition", "MISSING_STATE", "--state is required")
        result_mod.write(r, args.result)
        return 1

    if not trigger:
        r = result_mod.failure("statetree-add-transition", "MISSING_TRIGGER", "--trigger is required")
        result_mod.write(r, args.result)
        return 1

    if not target:
        r = result_mod.failure("statetree-add-transition", "MISSING_TARGET", "--target is required")
        result_mod.write(r, args.result)
        return 1

    try:
        data = _load_spec_for_edit(spec_path)
    except FileNotFoundError as exc:
        r = result_mod.failure("statetree-add-transition", "SPEC_NOT_FOUND", str(exc))
        result_mod.write(r, args.result)
        return 1
    except ValueError as exc:
        r = result_mod.failure("statetree-add-transition", "SPEC_ERROR", str(exc))
        result_mod.write(r, args.result)
        return 1

    states: list[dict] = data["statetree"].setdefault("states", [])
    state = _find_state(states, state_name)
    if not state:
        r = result_mod.failure(
            "statetree-add-transition", "STATE_NOT_FOUND",
            f"State '{state_name}' not found in spec",
        )
        result_mod.write(r, args.result)
        return 1

    transition = {"trigger": trigger, "target": target}
    state.setdefault("transitions", []).append(transition)
    _save_spec_yaml(spec_path, data)

    r = result_mod.success(
        "statetree-add-transition",
        f"Added transition '{trigger}→{target}' to state '{state_name}' in {spec_path}",
    )
    result_mod.write(r, args.result)
    print(f"PASS  ue-auto ai statetree add-transition  (state={state_name}, {trigger}→{target})")
    return 0


# ── add-condition ─────────────────────────────────────────────────────────────

def _cmd_statetree_add_condition(args: Any) -> int:
    spec_path = getattr(args, "spec", None)
    state_name = getattr(args, "state", None)
    trans_idx = getattr(args, "transition_index", None)
    cls = getattr(args, "cls", None)
    params_str = getattr(args, "params", None)

    if not spec_path:
        r = result_mod.failure("statetree-add-condition", "MISSING_SPEC", "--spec is required")
        result_mod.write(r, args.result)
        return 1

    if not state_name:
        r = result_mod.failure("statetree-add-condition", "MISSING_STATE", "--state is required")
        result_mod.write(r, args.result)
        return 1

    if not cls:
        r = result_mod.failure("statetree-add-condition", "MISSING_CLASS", "--class is required")
        result_mod.write(r, args.result)
        return 1

    try:
        data = _load_spec_for_edit(spec_path)
    except FileNotFoundError as exc:
        r = result_mod.failure("statetree-add-condition", "SPEC_NOT_FOUND", str(exc))
        result_mod.write(r, args.result)
        return 1
    except ValueError as exc:
        r = result_mod.failure("statetree-add-condition", "SPEC_ERROR", str(exc))
        result_mod.write(r, args.result)
        return 1

    states: list[dict] = data["statetree"].setdefault("states", [])
    state = _find_state(states, state_name)
    if not state:
        r = result_mod.failure(
            "statetree-add-condition", "STATE_NOT_FOUND",
            f"State '{state_name}' not found in spec",
        )
        result_mod.write(r, args.result)
        return 1

    transitions: list[dict] = state.get("transitions", [])
    if trans_idx is None or trans_idx < 0 or trans_idx >= len(transitions):
        r = result_mod.failure(
            "statetree-add-condition", "TRANSITION_NOT_FOUND",
            f"No transition at index {trans_idx} in state '{state_name}'",
        )
        result_mod.write(r, args.result)
        return 1

    params: dict = {}
    if params_str:
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError as exc:
            r = result_mod.failure("statetree-add-condition", "INVALID_PARAMS", str(exc))
            result_mod.write(r, args.result)
            return 1

    cond_entry: dict = {"class": cls, **params}
    transitions[trans_idx].setdefault("conditions", []).append(cond_entry)
    _save_spec_yaml(spec_path, data)

    r = result_mod.success(
        "statetree-add-condition",
        f"Added condition '{cls}' to transition[{trans_idx}] of '{state_name}' in {spec_path}",
    )
    result_mod.write(r, args.result)
    print(f"PASS  ue-auto ai statetree add-condition  (state={state_name}, class={cls})")
    return 0


# ── compile ───────────────────────────────────────────────────────────────────

def _cmd_statetree_compile(args: Any) -> int:
    project = getattr(args, "project", None)
    asset = getattr(args, "asset", None)

    if not project:
        r = result_mod.failure("statetree-compile", "MISSING_PROJECT", "--project is required")
        result_mod.write(r, args.result)
        return 1

    if not asset:
        r = result_mod.failure("statetree-compile", "MISSING_ASSET", "--asset is required")
        result_mod.write(r, args.result)
        return 1

    if getattr(args, "dry_run", False):
        r = result_mod.success("statetree-compile", f"[dry-run] Would compile {asset}", asset=asset)
        r["dry_run"] = True
        result_mod.write(r, args.result)
        print(f"DRY-RUN  ue-auto ai statetree compile  (asset={asset})")
        return 0

    editor = find_editor()
    if not editor:
        r = result_mod.failure(
            "statetree-compile", "EDITOR_NOT_FOUND",
            "UnrealEditor-Cmd not found",
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, args.result)
        return 1

    _out_raw = getattr(args, "out", None) or "Saved/AutomationReports/statetree.compile.result.json"
    out = Path(_out_raw).as_posix() if Path(_out_raw).is_absolute() else _out_raw

    cmd = [
        editor,
        str(Path(project).resolve()),
        "-run=StateTreeCompileCommandlet",
        f"-asset={asset}",
        f"-out={out}",
        "-unattended",
        "-nop4",
        "-nosplash",
        "-nullrhi",
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        r = result_mod.failure(
            "statetree-compile", "EDITOR_NOT_FOUND", str(exc),
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, args.result)
        return 1

    ok = proc.returncode == 0

    result_data: dict = {}
    result_path = Path(out) if Path(out).is_absolute() else Path(project).parent / out
    if result_path.exists():
        try:
            result_data = json.loads(result_path.read_text(encoding="utf-8"))
            ok = ok and bool(result_data.get("ok", False))
        except (json.JSONDecodeError, OSError):
            pass

    if ok:
        msg = result_data.get("message", f"StateTree compiled: {asset}")
        r = result_mod.success("statetree-compile", msg, asset=asset)
    else:
        if proc.stderr:
            print(proc.stderr[:500], file=sys.stderr)
        error_code = result_data.get("error_code", "COMPILE_FAILED")
        error_msg = (
            result_data.get("message")
            or f"StateTreeCompileCommandlet failed (exit {proc.returncode})"
        )
        r = result_mod.failure("statetree-compile", error_code, error_msg, asset=asset)
    result_mod.write(r, args.result)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto ai statetree compile  (asset={asset})")
    return 0 if ok else 1


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
    val_p = sub.add_parser(
        "validate",
        help="Validate StateTree structure (Dead State, Missing Target, No Exit, Duplicate, Evaluator, Spec)",
    )
    add_common(val_p)
    val_p.add_argument("--snapshot", metavar="PATH", help="statetree.snapshot.json path")
    val_p.add_argument("--spec", metavar="PATH", help="Wire spec YAML for SPEC_MISMATCH check (optional)")
    val_p.set_defaults(func=_cmd_statetree_validate)

    # create
    create_p = sub.add_parser("create", help="Generate Blueprint character + StateTree asset via UE Python")
    add_common(create_p)
    create_p.add_argument("--spec", metavar="PATH", help="Create spec YAML path")
    create_p.set_defaults(func=_cmd_statetree_create)

    # wire
    wire_p = sub.add_parser("wire", help="Wire StateTree states and compile via C++ commandlet")
    add_common(wire_p)
    wire_p.add_argument("--asset", metavar="PATH", help="UE asset path (e.g. /Game/AI/ST_EnemyAI)")
    wire_p.add_argument("--spec", metavar="PATH", help="Wire spec YAML (provides asset + state/task/condition config)")
    wire_p.set_defaults(func=_cmd_statetree_wire)

    # add-state
    as_p = sub.add_parser("add-state", help="Append a new state to a wire spec YAML")
    add_common(as_p)
    as_p.add_argument("--spec", metavar="PATH", required=True, help="Wire spec YAML to modify")
    as_p.add_argument("--name", metavar="NAME", required=True, help="State name to add")
    as_p.add_argument("--parent", metavar="NAME", help="Parent state name (optional)")
    as_p.set_defaults(func=_cmd_statetree_add_state)

    # add-task
    at_p = sub.add_parser("add-task", help="Append a task to a state in a wire spec YAML")
    add_common(at_p)
    at_p.add_argument("--spec", metavar="PATH", required=True, help="Wire spec YAML to modify")
    at_p.add_argument("--state", metavar="NAME", required=True, help="Target state name")
    at_p.add_argument("--class", metavar="CLASS", dest="cls", required=True, help="Task class name (e.g. FleeTask)")
    at_p.add_argument("--params", metavar="JSON", help='Task parameters as JSON (e.g. \'{"flee_distance": 800.0}\')')
    at_p.set_defaults(func=_cmd_statetree_add_task)

    # add-transition
    atr_p = sub.add_parser("add-transition", help="Append a transition to a state in a wire spec YAML")
    add_common(atr_p)
    atr_p.add_argument("--spec", metavar="PATH", required=True, help="Wire spec YAML to modify")
    atr_p.add_argument("--state", metavar="NAME", required=True, help="Source state name")
    atr_p.add_argument("--trigger", metavar="TRIGGER", required=True, help="Trigger type (OnTick, OnStateCompleted, OnEvent)")
    atr_p.add_argument("--target", metavar="NAME", required=True, help="Target state name")
    atr_p.set_defaults(func=_cmd_statetree_add_transition)

    # add-condition
    ac_p = sub.add_parser("add-condition", help="Append a condition to a transition in a wire spec YAML")
    add_common(ac_p)
    ac_p.add_argument("--spec", metavar="PATH", required=True, help="Wire spec YAML to modify")
    ac_p.add_argument("--state", metavar="NAME", required=True, help="State name")
    ac_p.add_argument("--transition-index", metavar="N", dest="transition_index", type=int, required=True, help="0-based transition index")
    ac_p.add_argument("--class", metavar="CLASS", dest="cls", required=True, help="Condition class name (e.g. IsPlayerNear)")
    ac_p.add_argument("--params", metavar="JSON", help='Condition parameters as JSON (e.g. \'{"radius": 500.0}\')')
    ac_p.set_defaults(func=_cmd_statetree_add_condition)

    # compile
    comp_p = sub.add_parser("compile", help="Compile a StateTree asset via C++ commandlet")
    add_common(comp_p)
    comp_p.add_argument("--asset", metavar="PATH", required=True, help="UE asset path (e.g. /Game/AI/ST_EnemyAI)")
    comp_p.set_defaults(func=_cmd_statetree_compile)
