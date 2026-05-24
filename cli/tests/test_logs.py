import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ue_auto.commands.logs_cmd import (
    LOG_PATTERNS,
    _cmd_logs_analyze,
    analyze_log_lines,
)


# ── LOG_PATTERNS ───────────────────────────────────────────────────────────────

def test_log_patterns_keys_exist():
    expected = {"UHT_ERROR", "COMPILE_ERROR", "LINK_ERROR", "MISSING_MODULE",
                "DEPRECATED_WARNING", "ASSET_WARNING"}
    assert expected == set(LOG_PATTERNS.keys())


# ── analyze_log_lines ──────────────────────────────────────────────────────────

def test_analyze_empty_log():
    results = analyze_log_lines([])
    assert results == []


def test_analyze_clean_log():
    lines = [
        "[2024.01.01-00.00.00:000][  0]LogInit: Starting UE4",
        "[2024.01.01-00.00.01:000][  0]LogInit: Build machine detected",
    ]
    results = analyze_log_lines(lines)
    assert results == []


def test_analyze_uht_error():
    lines = ["Error: [UHT] Missing required header 'SomeClass.h'"]
    results = analyze_log_lines(lines)
    assert len(results) == 1
    assert results[0]["category"] == "UHT_ERROR"


def test_analyze_compile_error():
    lines = ["error C2065: 'SomeVar': undeclared identifier"]
    results = analyze_log_lines(lines)
    assert len(results) == 1
    assert results[0]["category"] == "COMPILE_ERROR"


def test_analyze_link_error():
    lines = ["Error: LNK2019: unresolved external symbol _SomeFunc"]
    results = analyze_log_lines(lines)
    assert len(results) == 1
    assert results[0]["category"] == "LINK_ERROR"


def test_analyze_missing_module():
    lines = ["LogModuleManager: Warning: No module named 'MyPlugin' found"]
    results = analyze_log_lines(lines)
    assert len(results) == 1
    assert results[0]["category"] == "MISSING_MODULE"


def test_analyze_deprecated_warning():
    lines = ["Warning: DeprecatedFunction is deprecated and will be removed"]
    results = analyze_log_lines(lines)
    assert len(results) == 1
    assert results[0]["category"] == "DEPRECATED_WARNING"


def test_analyze_asset_warning():
    lines = ["LogAssetRegistry: Warning: Asset '/Game/Foo/Bar' has invalid data"]
    results = analyze_log_lines(lines)
    assert len(results) == 1
    assert results[0]["category"] == "ASSET_WARNING"


def test_analyze_multiple_errors():
    lines = [
        "error C2065: undeclared identifier",
        "Error: LNK2019: unresolved external symbol",
        "[INFO] Build complete",
    ]
    results = analyze_log_lines(lines)
    assert len(results) == 2
    categories = {r["category"] for r in results}
    assert "COMPILE_ERROR" in categories
    assert "LINK_ERROR" in categories


def test_analyze_result_has_line_field():
    lines = ["error C2065: undeclared identifier"]
    results = analyze_log_lines(lines)
    assert "line" in results[0]
    assert results[0]["line"] == lines[0]


def test_analyze_result_has_lineno_field():
    lines = ["clean line", "error C2065: undeclared identifier"]
    results = analyze_log_lines(lines)
    assert results[0]["lineno"] == 2


# ── _cmd_logs_analyze ──────────────────────────────────────────────────────────

class _Args:
    def __init__(self, **kw):
        self.log = kw.get("log", "Saved/Logs/UnrealEditor.log")
        self.result = kw.get("result", "Saved/AutomationReports/result.json")
        self.out = kw.get("out", None)


def test_cmd_logs_analyze_clean_log(tmp_path):
    log_file = tmp_path / "clean.log"
    log_file.write_text("[INFO] Build started\n[INFO] Build complete\n")
    result_path = tmp_path / "result.json"

    ret = _cmd_logs_analyze(_Args(log=str(log_file), result=str(result_path)))

    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert data["action"] == "logs"


def test_cmd_logs_analyze_error_log_returns_1(tmp_path):
    log_file = tmp_path / "error.log"
    log_file.write_text("error C2065: undeclared identifier\n")
    result_path = tmp_path / "result.json"

    ret = _cmd_logs_analyze(_Args(log=str(log_file), result=str(result_path)))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_logs_analyze_empty_log(tmp_path):
    log_file = tmp_path / "empty.log"
    log_file.write_text("")
    result_path = tmp_path / "result.json"

    ret = _cmd_logs_analyze(_Args(log=str(log_file), result=str(result_path)))

    assert ret == 0


def test_cmd_logs_analyze_missing_file(tmp_path):
    result_path = tmp_path / "result.json"

    ret = _cmd_logs_analyze(_Args(log=str(tmp_path / "missing.log"), result=str(result_path)))

    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_logs_analyze_writes_markdown(tmp_path):
    log_file = tmp_path / "error.log"
    log_file.write_text("error C2065: undeclared identifier\n")
    result_path = tmp_path / "result.json"
    out_path = tmp_path / "logs.md"

    _cmd_logs_analyze(_Args(log=str(log_file), result=str(result_path), out=str(out_path)))

    assert out_path.exists()
    content = out_path.read_text()
    assert "COMPILE_ERROR" in content


def test_cmd_logs_analyze_result_contains_findings(tmp_path):
    log_file = tmp_path / "error.log"
    log_file.write_text("error C2065: undeclared\nError: LNK2019: unresolved\n")
    result_path = tmp_path / "result.json"

    _cmd_logs_analyze(_Args(log=str(log_file), result=str(result_path)))

    data = json.loads(result_path.read_text())
    assert "findings" in data
    assert len(data["findings"]) == 2
