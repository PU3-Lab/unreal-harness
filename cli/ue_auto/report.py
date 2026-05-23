from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ReportBuilder:
    def __init__(self, title: str, action: str):
        self._lines: list[str] = [f"# ue-auto Report — {title}", ""]
        self._action = action
        self._status = "PASS"

    def status(self, status: str) -> "ReportBuilder":
        self._status = status
        return self

    def add_section(self, heading: str, lines: list[str]) -> "ReportBuilder":
        self._lines += [f"## {heading}", ""]
        self._lines += lines
        self._lines.append("")
        return self

    def add_checks(self, checks: list[dict[str, Any]]) -> "ReportBuilder":
        self._lines += ["## Checks", "", "| Check | Result |", "|---|---|"]
        for c in checks:
            icon = "PASS" if c.get("ok") else "FAIL"
            self._lines.append(f"| {c['name']} | {icon} |")
        self._lines.append("")
        return self

    def build(self) -> str:
        status_line = f"**Status**: {self._status}  \n**Time**: {_now()}"
        return "\n".join([self._lines[0], "", status_line, ""] + self._lines[2:])


def write(content: str, path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
