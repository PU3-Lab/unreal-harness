import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from ue_auto.commands.status_cmd import _load_results, _cmd_status


def _write_result(tmp_path: Path, filename: str, data: dict) -> None:
    (tmp_path / filename).write_text(json.dumps(data), encoding="utf-8")


def test_load_results_empty_dir(tmp_path):
    assert _load_results(str(tmp_path)) == []


def test_load_results_returns_sorted_by_timestamp(tmp_path):
    _write_result(tmp_path, "b.result.json", {"action": "b", "ok": True, "timestamp": "2026-05-24T10:00:00Z"})
    _write_result(tmp_path, "a.result.json", {"action": "a", "ok": True, "timestamp": "2026-05-24T09:00:00Z"})

    results = _load_results(str(tmp_path))
    assert [r["action"] for r in results] == ["a", "b"]


def test_load_results_skips_invalid_json(tmp_path):
    (tmp_path / "bad.result.json").write_text("not json", encoding="utf-8")
    _write_result(tmp_path, "good.result.json", {"action": "ping", "ok": True, "timestamp": "2026-05-24T09:00:00Z"})

    results = _load_results(str(tmp_path))
    assert len(results) == 1
    assert results[0]["action"] == "ping"


def test_cmd_status_no_results(tmp_path, capsys):
    args = MagicMock()
    args.reports_dir = str(tmp_path)

    code = _cmd_status(args)

    assert code == 0
    assert "No results found" in capsys.readouterr().out


def test_cmd_status_all_pass(tmp_path, capsys):
    _write_result(tmp_path, "ping.result.json", {"action": "ping", "ok": True, "message": "pong", "timestamp": "2026-05-24T09:00:00Z"})
    _write_result(tmp_path, "asset-snapshot.result.json", {"action": "snapshot", "ok": True, "message": "done", "timestamp": "2026-05-24T09:01:00Z"})

    args = MagicMock()
    args.reports_dir = str(tmp_path)

    code = _cmd_status(args)
    out = capsys.readouterr().out

    assert code == 0
    assert "PASS" in out
    assert "PASS 2" in out
    assert "FAIL 0" in out


def test_cmd_status_with_failures(tmp_path, capsys):
    _write_result(tmp_path, "ping.result.json", {"action": "ping", "ok": True, "message": "pong", "timestamp": "2026-05-24T09:00:00Z"})
    _write_result(tmp_path, "validate.result.json", {
        "action": "validate", "ok": False,
        "error": {"code": "FAIL", "message": "59 violations"},
        "timestamp": "2026-05-24T09:02:00Z",
    })

    args = MagicMock()
    args.reports_dir = str(tmp_path)

    code = _cmd_status(args)
    out = capsys.readouterr().out

    assert code == 1
    assert "FAIL" in out
    assert "59 violations" in out


def test_cmd_status_shows_check_count(tmp_path, capsys):
    _write_result(tmp_path, "validate.result.json", {
        "action": "validate", "ok": False,
        "error": {"code": "FAIL", "message": "violations found"},
        "checks": [{"type": "PREFIX_VIOLATION"}] * 5,
        "timestamp": "2026-05-24T09:00:00Z",
    })

    args = MagicMock()
    args.reports_dir = str(tmp_path)

    _cmd_status(args)
    out = capsys.readouterr().out

    assert "[5 issues]" in out
