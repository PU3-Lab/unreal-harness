import json
from pathlib import Path

import pytest

from ue_auto.commands.review import _cmd_review_summarize


class _Args:
    def __init__(self, **kw):
        self.reports = kw.get("reports", "Saved/AutomationReports")
        self.logs = kw.get("logs", "Saved/Logs")
        self.result = kw.get("result", "Saved/AutomationReports/result.json")
        self.out = kw.get("out", None)
        self.out_json = kw.get("out_json", None)


# ── _cmd_review_summarize ──────────────────────────────────────────────────────

def test_cmd_review_summarize_empty_reports_dir_passes(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    result_path = tmp_path / "result.json"

    ret = _cmd_review_summarize(_Args(
        reports=str(reports_dir),
        result=str(result_path),
        out=str(tmp_path / "summary.md"),
        out_json=str(tmp_path / "summary.json"),
    ))

    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_cmd_review_summarize_nonexistent_dir_passes(tmp_path):
    result_path = tmp_path / "result.json"

    ret = _cmd_review_summarize(_Args(
        reports=str(tmp_path / "nonexistent"),
        result=str(result_path),
        out_json=str(tmp_path / "summary.json"),
    ))

    assert ret == 0


def test_cmd_review_summarize_all_ok_returns_pass(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "a.json").write_text(json.dumps({"ok": True, "action": "diff"}))
    (reports_dir / "b.json").write_text(json.dumps({"ok": True, "action": "logs"}))
    result_path = tmp_path / "result.json"

    ret = _cmd_review_summarize(_Args(
        reports=str(reports_dir),
        result=str(result_path),
        out_json=str(tmp_path / "summary.json"),
    ))

    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert data["summary"]["status"] == "PASS"


def test_cmd_review_summarize_one_failure_returns_fail(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "a.json").write_text(json.dumps({"ok": True, "action": "diff"}))
    (reports_dir / "b.json").write_text(
        json.dumps({"ok": False, "action": "build", "error": {"message": "Build failed"}})
    )
    result_path = tmp_path / "result.json"

    ret = _cmd_review_summarize(_Args(
        reports=str(reports_dir),
        result=str(result_path),
        out_json=str(tmp_path / "summary.json"),
    ))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert data["summary"]["status"] == "FAIL"
    assert data["summary"]["errors"] == 1


def test_cmd_review_summarize_excludes_summary_json(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "review.summary.json").write_text(
        json.dumps({"ok": False, "action": "summarize"})
    )
    result_path = tmp_path / "result.json"

    ret = _cmd_review_summarize(_Args(
        reports=str(reports_dir),
        result=str(result_path),
        out_json=str(tmp_path / "summary.json"),
    ))

    assert ret == 0


def test_cmd_review_summarize_writes_summary_json(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "a.json").write_text(json.dumps({"ok": True, "action": "diff"}))
    out_json = tmp_path / "summary.json"

    _cmd_review_summarize(_Args(
        reports=str(reports_dir),
        result=str(tmp_path / "result.json"),
        out_json=str(out_json),
    ))

    assert out_json.exists()
    summary = json.loads(out_json.read_text())
    assert "status" in summary
    assert "reports_scanned" in summary


def test_cmd_review_summarize_writes_markdown(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "a.json").write_text(json.dumps({"ok": True, "action": "diff"}))
    out_md = tmp_path / "summary.md"

    _cmd_review_summarize(_Args(
        reports=str(reports_dir),
        result=str(tmp_path / "result.json"),
        out=str(out_md),
        out_json=str(tmp_path / "summary.json"),
    ))

    assert out_md.exists()
    content = out_md.read_text()
    assert "PASS" in content


def test_cmd_review_summarize_malformed_json_skipped(tmp_path):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    (reports_dir / "bad.json").write_text("not valid json{{{{")
    (reports_dir / "good.json").write_text(json.dumps({"ok": True, "action": "diff"}))
    result_path = tmp_path / "result.json"

    ret = _cmd_review_summarize(_Args(
        reports=str(reports_dir),
        result=str(result_path),
        out_json=str(tmp_path / "summary.json"),
    ))

    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["summary"]["reports_scanned"] == 1
