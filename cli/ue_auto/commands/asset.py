import argparse
import sys
from typing import Callable

from ue_auto import result as result_mod


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    for verb in ("snapshot", "validate"):
        p = sub.add_parser(verb, help=f"[Sprint 2 stub] {verb}")
        add_common(p)
        p.set_defaults(func=_make_stub(verb))


def _make_stub(verb: str):
    def _stub(args):
        print(f"ue-auto asset {verb}: not yet implemented (Sprint 2)", file=sys.stderr)
        r = result_mod.failure(
            verb, "NOT_IMPLEMENTED", f"asset {verb} is planned for Sprint 2"
        )
        result_mod.write(r, args.result)
        return 1
    return _stub
