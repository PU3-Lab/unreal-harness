import argparse
import sys

from ue_auto.commands import ai_statetree, asset, build_cmd, logs_cmd, review, status_cmd, test_cmd, validate_cmd


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", metavar="PATH", help=".uproject file path")
    parser.add_argument("--out", metavar="PATH", help="primary output path")
    parser.add_argument("--out-md", metavar="PATH", dest="out_md", help="Markdown output path")
    parser.add_argument("--out-json", metavar="PATH", dest="out_json", help="JSON output path")
    parser.add_argument(
        "--result",
        metavar="PATH",
        default=None,
        help="result.json output path (default: Saved/AutomationReports/<action>.result.json)",
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

    # ── review ────────────────────────────────────────────────────
    review_p = subparsers.add_parser("review", help="Review and risk analysis domain")
    review_sub = review_p.add_subparsers(dest="action", required=True)
    review.register(review_sub, _add_common_leaf)

    # ── build ─────────────────────────────────────────────────────
    build_p = subparsers.add_parser("build", help="Build domain")
    build_sub = build_p.add_subparsers(dest="action", required=True)
    build_cmd.register(build_sub, _add_common_leaf)

    # ── logs ──────────────────────────────────────────────────────
    logs_p = subparsers.add_parser("logs", help="Log analysis domain")
    logs_sub = logs_p.add_subparsers(dest="action", required=True)
    logs_cmd.register(logs_sub, _add_common_leaf)

    # ── test ──────────────────────────────────────────────────────
    test_p = subparsers.add_parser("test", help="Test automation domain")
    test_sub = test_p.add_subparsers(dest="action", required=True)
    test_cmd.register(test_sub, _add_common_leaf)

    # ── validate ──────────────────────────────────────────────────
    validate_p = subparsers.add_parser("validate", help="Validation domain")
    validate_sub = validate_p.add_subparsers(dest="action", required=True)
    validate_cmd.register(validate_sub, _add_common_leaf)

    # ── status ────────────────────────────────────────────────────
    status_cmd.register(subparsers, _add_common_leaf)

    args = parser.parse_args()
    if args.apply:
        args.dry_run = False

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    sys.exit(args.func(args) or 0)
