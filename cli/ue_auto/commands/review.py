import argparse
import json
import subprocess
from pathlib import Path
from typing import Callable

from ue_auto import report as report_mod
from ue_auto import result as result_mod


def classify_risk(filepath: str) -> str:
    p = Path(filepath)
    ext = p.suffix.lstrip(".").lower()

    if ext in ("uasset", "umap"):
        return "HIGH"

    if ext == "ini":
        normalized = filepath.replace("\\", "/")
        if "/Config/" in normalized or normalized.startswith("Config/"):
            return "HIGH"

    if p.name.endswith(".Build.cs"):
        return "MEDIUM"

    if ext in ("cpp", "h", "hpp"):
        return "MEDIUM"

    return "LOW"


def get_changed_files(base: str, head: str = "HEAD") -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}..{head}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [f for f in result.stdout.splitlines() if f.strip()]


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    _reg_diff(sub, add_common)
    _reg_summarize(sub, add_common)


def _reg_diff(sub, add_common):
    p = sub.add_parser("diff", help="Git diff risk report")
    add_common(p)
    p.add_argument("--base", metavar="REF", default="main", help="Base branch/commit (default: main)")
    p.add_argument("--head", metavar="REF", default="HEAD", help="Head commit (default: HEAD)")
    p.set_defaults(func=_cmd_review_diff)


def _reg_summarize(sub, add_common):
    p = sub.add_parser("summarize", help="Aggregate reports into review.summary")
    add_common(p)
    p.add_argument("--reports", metavar="DIR", default="Saved/AutomationReports",
                   help="Reports directory (default: Saved/AutomationReports)")
    p.add_argument("--logs", metavar="DIR", default="Saved/Logs",
                   help="Logs directory (default: Saved/Logs)")
    p.set_defaults(func=_cmd_review_summarize)


# ── diff ───────────────────────────────────────────────────────────────────────

def _cmd_review_diff(args) -> int:
    base = getattr(args, "base", "main") or "main"
    head = getattr(args, "head", "HEAD") or "HEAD"

    try:
        files = get_changed_files(base, head)
    except subprocess.CalledProcessError as e:
        r = result_mod.failure("diff", "GIT_ERROR", str(e),
                               hint="Ensure git is installed and the base ref exists.")
        result_mod.write(r, args.result)
        return 1

    classified = [(f, classify_risk(f)) for f in files]
    high   = [f for f, risk in classified if risk == "HIGH"]
    medium = [f for f, risk in classified if risk == "MEDIUM"]
    low    = [f for f, risk in classified if risk == "LOW"]

    r = result_mod.success(
        "diff",
        f"{len(files)} files changed",
        checks=[
            {"name": "high_risk_files",   "ok": len(high) == 0, "count": len(high)},
            {"name": "medium_risk_files", "ok": True,            "count": len(medium)},
            {"name": "low_risk_files",    "ok": True,            "count": len(low)},
        ],
    )
    r["risk"] = {
        "high":   [{"file": f} for f in high],
        "medium": [{"file": f} for f in medium],
        "low":    [{"file": f} for f in low],
    }
    result_mod.write(r, args.result)

    status = "WARN" if high else "PASS"
    if out := getattr(args, "out", None) or getattr(args, "out_md", None):
        sections: list[str] = []
        for label, bucket in (("HIGH", high), ("MEDIUM", medium), ("LOW", low)):
            if bucket:
                sections.append(f"### {label} Risk")
                sections.extend(f"- `{f}`" for f in bucket)
                sections.append("")
        rpt = (
            report_mod.ReportBuilder("review diff", "diff")
            .status(status)
            .add_section("Summary", [
                f"- Base: `{base}` → Head: `{head}`",
                f"- Total: {len(files)} files  |  HIGH: {len(high)}  MEDIUM: {len(medium)}  LOW: {len(low)}",
            ])
            .add_section("Risk Details", sections or ["_No changes found._"])
            .build()
        )
        report_mod.write(rpt, out)

    print(f"{status}  ue-auto review diff  "
          f"({len(high)} HIGH, {len(medium)} MEDIUM, {len(low)} LOW)")
    return 0


# ── summarize ──────────────────────────────────────────────────────────────────

def _cmd_review_summarize(args) -> int:
    reports_dir = Path(getattr(args, "reports", "Saved/AutomationReports"))
    out_md  = getattr(args, "out", None) or str(reports_dir / "review.summary.md")
    out_json = getattr(args, "out_json", None) or str(reports_dir / "review.summary.json")

    report_results: list[dict] = []
    if reports_dir.exists():
        for json_file in sorted(reports_dir.glob("*.json")):
            if json_file.name in ("review.summary.json",):
                continue
            try:
                report_results.append(json.loads(json_file.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                pass

    errors = [r for r in report_results if not r.get("ok")]
    status = "FAIL" if errors else "PASS"
    overall_ok = not bool(errors)

    summary = {
        "status": status,
        "reports_scanned": len(report_results),
        "errors": len(errors),
        "error_details": [
            {"action": r.get("action"), "error": r.get("error")}
            for r in errors
        ],
    }

    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if overall_ok:
        r = result_mod.success("summarize", f"Review complete: {status}")
    else:
        r = result_mod.failure(
            "summarize", "REVIEW_FAILED",
            f"{len(errors)} result(s) failed",
            hint="Check error_details for failing actions.",
        )
    r["summary"] = summary
    result_mod.write(r, args.result)

    builder = (
        report_mod.ReportBuilder("review summarize", "summarize")
        .status(status)
        .add_section("Overview", [
            f"- Reports scanned: {len(report_results)}",
            f"- Errors: {len(errors)}",
            f"- Status: **{status}**",
        ])
    )
    if errors:
        builder.add_section("Errors", [
            f"- `{e.get('action', 'unknown')}`: "
            f"{(e.get('error') or {}).get('message', 'unknown error')}"
            for e in errors
        ])
    builder.add_section("Manual Checklist", [
        "- [ ] Visual QA in UE Editor",
        "- [ ] Blueprint compile errors checked",
        "- [ ] Game play-tested in PIE",
    ])
    report_mod.write(builder.build(), out_md)

    print(f"{status}  ue-auto review summarize  "
          f"({len(errors)} errors, {len(report_results)} reports scanned)")
    return 0 if overall_ok else 1
