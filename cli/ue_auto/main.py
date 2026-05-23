import argparse
import sys

from ue_auto.commands import ai_statetree, asset


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", metavar="PATH", help=".uproject file path")
    parser.add_argument("--out", metavar="PATH", help="primary output path")
    parser.add_argument("--out-md", metavar="PATH", dest="out_md", help="Markdown output path")
    parser.add_argument("--out-json", metavar="PATH", dest="out_json", help="JSON output path")
    parser.add_argument(
        "--result",
        metavar="PATH",
        default="Saved/AutomationReports/result.json",
        help="result.json output path (default: Saved/AutomationReports/result.json)",
    )
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    parser.add_argument("--apply", dest="apply", action="store_true", default=False)


def _add_common_leaf(parser: argparse.ArgumentParser) -> None:
    """Like _add_common but uses SUPPRESS defaults so root-level values are not clobbered."""
    S = argparse.SUPPRESS
    parser.add_argument("--project", metavar="PATH", help=".uproject file path", default=S)
    parser.add_argument("--out", metavar="PATH", help="primary output path", default=S)
    parser.add_argument("--out-md", metavar="PATH", dest="out_md", help="Markdown output path", default=S)
    parser.add_argument("--out-json", metavar="PATH", dest="out_json", help="JSON output path", default=S)
    parser.add_argument("--result", metavar="PATH", default=S, help="result.json output path")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=S)
    parser.add_argument("--apply", dest="apply", action="store_true", default=S)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ue-auto",
        description="UE5 automation harness CLI",
    )
    _add_common(parser)
    subparsers = parser.add_subparsers(dest="domain", required=True)

    # ── ai statetree ──────────────────────────────────────────────
    ai_p = subparsers.add_parser("ai", help="AI / behaviour tree domain")
    ai_sub = ai_p.add_subparsers(dest="subdomain", required=True)

    st_p = ai_sub.add_parser("statetree", help="StateTree commands")
    st_sub = st_p.add_subparsers(dest="action", required=True)
    ai_statetree.register(st_sub, _add_common_leaf)

    # ── asset ─────────────────────────────────────────────────────
    asset_p = subparsers.add_parser("asset", help="Asset naming / path domain")
    asset_sub = asset_p.add_subparsers(dest="action", required=True)
    asset.register(asset_sub, _add_common_leaf)

    args = parser.parse_args()
    if args.apply:
        args.dry_run = False

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args) or 0)
