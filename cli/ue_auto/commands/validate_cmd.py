import argparse
from typing import Callable

from ue_auto import result as result_mod


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    p = sub.add_parser("all", help="Run all domain validators (stub)")
    add_common(p)
    p.set_defaults(func=_cmd_validate_all)


def _cmd_validate_all(args) -> int:
    project = getattr(args, "project", None)
    if not project:
        r = result_mod.failure("validate", "MISSING_PROJECT", "--project is required",
                               hint="Pass --project path/to/MyGame.uproject")
        result_mod.write(r, args.result)
        return 1

    r = result_mod.success("validate", "no domain validators registered (Sprint 1 stub)")
    result_mod.write(r, args.result)
    print("WARN  ue-auto validate all  (no domain validators registered)")
    return 0
