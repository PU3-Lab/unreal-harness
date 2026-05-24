import argparse
import json
from pathlib import Path
from typing import Callable

from ue_auto import result as result_mod


def _load_results(reports_dir: str) -> list[dict]:
    results = []
    for p in sorted(Path(reports_dir).glob("*.result.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            data["_file"] = p.name
            results.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return sorted(results, key=lambda r: r.get("timestamp", ""))


def _cmd_status(args) -> int:
    reports_dir = getattr(args, "reports_dir", None) or result_mod.REPORTS_DIR
    results = _load_results(reports_dir)

    if not results:
        print(f"No results found in {reports_dir}")
        return 0

    col_action = max(len(r.get("action", "")) for r in results)
    col_action = max(col_action, 6)

    header = f"{'STATUS':<6}  {'ACTION':<{col_action}}  {'MESSAGE'}"
    print(header)
    print("-" * (len(header) + 20))

    for r in results:
        status = "PASS" if r.get("ok") else "FAIL"
        action = r.get("action", "?")
        ts = r.get("timestamp", "")[:19].replace("T", " ")

        if r.get("ok"):
            message = r.get("message", "")
        else:
            err = r.get("error", {})
            message = err.get("message", r.get("message", ""))

        checks = r.get("checks", [])
        if checks:
            message += f"  [{len(checks)} issues]"

        print(f"{status:<6}  {action:<{col_action}}  {message}  ({ts})")

    total = len(results)
    passed = sum(1 for r in results if r.get("ok"))
    failed = total - passed
    print()
    print(f"총 {total}개  PASS {passed}  FAIL {failed}")
    return 0 if failed == 0 else 1


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    p = sub.add_parser("status", help="Show all command results")
    add_common(p)
    p.add_argument(
        "--reports-dir",
        metavar="PATH",
        dest="reports_dir",
        help=f"reports directory (default: {result_mod.REPORTS_DIR})",
    )
    p.set_defaults(func=_cmd_status)
