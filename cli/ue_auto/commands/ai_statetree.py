import argparse
import json
import sys
from pathlib import Path
from typing import Callable

from ue_auto import result as result_mod, report as report_mod, runner


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    _reg_ping(sub, add_common)
    for verb in ("snapshot", "report", "validate", "create", "add-state", "add-task",
                 "add-transition", "add-condition", "compile"):
        _reg_stub(sub, add_common, verb)


def _reg_ping(sub, add_common):
    p = sub.add_parser("ping", help="Verify CLI→Editor pipeline end-to-end")
    add_common(p)
    p.set_defaults(func=_cmd_ping)


def _reg_stub(sub, add_common, verb):
    p = sub.add_parser(verb, help=f"[Sprint 0 stub] {verb}")
    add_common(p)
    p.set_defaults(func=_make_stub(verb))


def _make_stub(verb: str):
    def _stub(args):
        print(f"ue-auto ai statetree {verb}: not yet implemented (Sprint 0 stub)", file=sys.stderr)
        r = result_mod.failure(
            verb, "NOT_IMPLEMENTED", f"{verb} is not implemented in Sprint 0"
        )
        result_mod.write(r, args.result)
        return 1
    return _stub


def _cmd_ping(args) -> int:
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
        exit_code = runner.run_commandlet(
            project,
            "UEAutoPingCommandlet",
            timeout=60,
        )
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
    status = "PASS" if overall_ok else "FAIL"

    if overall_ok:
        r = result_mod.success("ping", "pong", checks=checks)
    else:
        r = result_mod.failure(
            "ping", "PING_FAILED", "One or more checks failed",
            hint="Check UE Editor logs in Saved/Logs/.",
        )
        r["checks"] = checks

    result_mod.write(r, args.result)

    if out := getattr(args, "out", None) or getattr(args, "out_md", None):
        rpt = (
            report_mod.ReportBuilder("ai statetree ping", "ping")
            .status(status)
            .add_section("Summary", [
                f"- Project: `{project}`",
                f"- Commandlet: `UEAuto.PingCommandlet`",
            ])
            .add_checks(checks)
            .build()
        )
        report_mod.write(rpt, out)

    if not overall_ok:
        print(f"FAIL  ue-auto ai statetree ping", file=sys.stderr)
        return 1

    print(f"PASS  ue-auto ai statetree ping")
    return 0
