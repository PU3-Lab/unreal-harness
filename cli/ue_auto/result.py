import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def success(
    action: str,
    message: str,
    *,
    asset: str | None = None,
    snapshot: str | None = None,
    checks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    r: dict[str, Any] = {"ok": True, "action": action, "message": message, "timestamp": _now()}
    if asset:
        r["asset"] = asset
    if snapshot:
        r["snapshot"] = snapshot
    if checks is not None:
        r["checks"] = checks
    return r


def failure(
    action: str,
    code: str,
    message: str,
    *,
    asset: str | None = None,
    hint: str | None = None,
) -> dict[str, Any]:
    r: dict[str, Any] = {
        "ok": False,
        "action": action,
        "error": {"code": code, "message": message},
        "timestamp": _now(),
    }
    if asset:
        r["asset"] = asset
    if hint:
        r["hint"] = hint
    return r


def write(result: dict[str, Any], path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
