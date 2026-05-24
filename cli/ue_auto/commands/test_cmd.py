import argparse
import subprocess
from pathlib import Path
from typing import Callable

from ue_auto import report as report_mod
from ue_auto import result as result_mod
from ue_auto.runner import find_editor


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    p = sub.add_parser("automation", help="Run UE automation tests")
    add_common(p)
    p.add_argument("--filter", metavar="FILTER", default=None,
                   help="Test filter (e.g. MyGame.Tests)")
    p.add_argument("--timeout", metavar="SEC", type=int, default=300,
                   help="Timeout in seconds (default: 300)")
    p.set_defaults(func=_cmd_test_automation)


def _cmd_test_automation(args) -> int:
    project = getattr(args, "project", None)
    if not project:
        r = result_mod.failure("test", "MISSING_PROJECT", "--project is required",
                               hint="Pass --project path/to/MyGame.uproject")
        result_mod.write(r, args.result)
        return 1

    editor = find_editor()
    if not editor:
        r = result_mod.failure(
            "test", "EDITOR_NOT_FOUND",
            "UnrealEditor-Cmd not found",
            hint="Set UE_EDITOR_CMD env var or install UE in the standard path.",
        )
        result_mod.write(r, args.result)
        return 1

    test_filter = getattr(args, "filter", None)
    timeout = getattr(args, "timeout", 300) or 300

    cmd = [
        editor,
        str(Path(project).resolve()),
        "-run=AutomationCommandlet",
        "-unattended",
        "-nop4",
        "-nosplash",
        "-nullrhi",
    ]
    if test_filter:
        cmd.append(f"-filter={test_filter}")

    try:
        proc = subprocess.run(cmd, timeout=timeout)
        ok = proc.returncode == 0
    except subprocess.TimeoutExpired:
        r = result_mod.failure(
            "test", "TIMEOUT",
            f"Automation tests timed out after {timeout}s",
        )
        result_mod.write(r, args.result)
        return 1

    if ok:
        r = result_mod.success("test", "Automation tests passed")
    else:
        r = result_mod.failure(
            "test", "TEST_FAILED",
            f"Automation tests failed with exit code {proc.returncode}",
        )

    result_mod.write(r, args.result)

    status = "PASS" if ok else "FAIL"
    print(f"{status}  ue-auto test automation  (filter={test_filter or 'all'})")
    return 0 if ok else 1
