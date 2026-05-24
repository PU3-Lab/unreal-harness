import argparse
import re
from pathlib import Path
from typing import Callable

from ue_auto import report as report_mod
from ue_auto import result as result_mod

LOG_PATTERNS: dict[str, re.Pattern[str]] = {
    "UHT_ERROR":          re.compile(r"Error:.*\[UHT\]", re.IGNORECASE),
    "COMPILE_ERROR":      re.compile(r"\berror\s+[A-Z]+\d+\b", re.IGNORECASE),
    "LINK_ERROR":         re.compile(r"\bLNK\d{4}\b", re.IGNORECASE),
    "MISSING_MODULE":     re.compile(r"No module named .+ found", re.IGNORECASE),
    "DEPRECATED_WARNING": re.compile(r"\bdeprecated\b", re.IGNORECASE),
    "ASSET_WARNING":      re.compile(r"LogAssetRegistry:.*Warning", re.IGNORECASE),
}


def analyze_log_lines(lines: list[str]) -> list[dict]:
    findings: list[dict] = []
    for lineno, line in enumerate(lines, start=1):
        for category, pattern in LOG_PATTERNS.items():
            if pattern.search(line):
                findings.append({"category": category, "lineno": lineno, "line": line})
                break
    return findings


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    p = sub.add_parser("analyze", help="Analyze UE log for errors and warnings")
    add_common(p)
    p.add_argument("--log", metavar="FILE", default="Saved/Logs/UnrealEditor.log",
                   help="Log file to analyze (default: Saved/Logs/UnrealEditor.log)")
    p.set_defaults(func=_cmd_logs_analyze)


def _cmd_logs_analyze(args) -> int:
    log_path = Path(getattr(args, "log", "Saved/Logs/UnrealEditor.log"))

    if not log_path.exists():
        r = result_mod.failure(
            "logs", "FILE_NOT_FOUND", f"Log file not found: {log_path}",
            hint="Pass --log with the correct path.",
        )
        result_mod.write(r, args.result)
        return 1

    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    findings = analyze_log_lines(lines)

    errors = [f for f in findings if f["category"] not in ("DEPRECATED_WARNING", "ASSET_WARNING")]
    has_errors = bool(errors)

    checks = [
        {"name": cat, "ok": not any(f["category"] == cat for f in findings), "count": sum(1 for f in findings if f["category"] == cat)}
        for cat in LOG_PATTERNS
    ]

    if has_errors:
        r = result_mod.failure(
            "logs", "LOG_ERRORS",
            f"{len(errors)} error(s) found in log",
            hint="Review the findings list for details.",
        )
    else:
        r = result_mod.success("logs", f"Log analyzed: {len(findings)} finding(s)", checks=checks)

    r["findings"] = findings
    result_mod.write(r, args.result)

    status = "FAIL" if has_errors else "PASS"
    out = getattr(args, "out", None)
    if out:
        by_cat: dict[str, list[dict]] = {}
        for f in findings:
            by_cat.setdefault(f["category"], []).append(f)

        sections: list[str] = []
        for cat, items in by_cat.items():
            sections.append(f"### {cat}")
            sections.extend(f"- L{item['lineno']}: `{item['line'].strip()}`" for item in items[:10])
            if len(items) > 10:
                sections.append(f"  _…and {len(items) - 10} more_")
            sections.append("")

        rpt = (
            report_mod.ReportBuilder("logs analyze", "logs")
            .status(status)
            .add_section("Summary", [
                f"- Log file: `{log_path}`",
                f"- Total findings: {len(findings)}  |  Errors: {len(errors)}",
            ])
            .add_section("Findings", sections or ["_No issues found._"])
            .build()
        )
        report_mod.write(rpt, out)

    print(f"{status}  ue-auto logs analyze  ({len(findings)} findings, {len(errors)} errors)")
    return 1 if has_errors else 0
