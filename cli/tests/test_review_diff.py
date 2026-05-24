import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ue_auto.commands.review import _cmd_review_diff, classify_risk, get_changed_files


# ── classify_risk ──────────────────────────────────────────────────────────────

def test_classify_risk_uasset():
    assert classify_risk("Content/Characters/SK_Hero.uasset") == "HIGH"


def test_classify_risk_umap():
    assert classify_risk("Content/Maps/L_World.umap") == "HIGH"


def test_classify_risk_config_ini():
    assert classify_risk("Config/DefaultGame.ini") == "HIGH"


def test_classify_risk_gameplay_tags_ini():
    assert classify_risk("Config/DefaultGameplayTags.ini") == "HIGH"


def test_classify_risk_nested_config_ini():
    assert classify_risk("MyProject/Config/DefaultEngine.ini") == "HIGH"


def test_classify_risk_build_cs():
    assert classify_risk("Source/MyGame/MyGame.Build.cs") == "MEDIUM"


def test_classify_risk_cpp():
    assert classify_risk("Source/MyGame/MyActor.cpp") == "MEDIUM"


def test_classify_risk_header():
    assert classify_risk("Source/MyGame/MyActor.h") == "MEDIUM"


def test_classify_risk_hpp():
    assert classify_risk("Source/MyGame/MyActor.hpp") == "MEDIUM"


def test_classify_risk_markdown():
    assert classify_risk("README.md") == "LOW"


def test_classify_risk_python():
    assert classify_risk("scripts/tool.py") == "LOW"


def test_classify_risk_json():
    assert classify_risk("Docs/spec.json") == "LOW"


# ── get_changed_files ──────────────────────────────────────────────────────────

def test_get_changed_files_returns_list():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="file1.cpp\nfile2.uasset\n")
        files = get_changed_files("main")
    assert files == ["file1.cpp", "file2.uasset"]


def test_get_changed_files_empty():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="")
        files = get_changed_files("main")
    assert files == []


def test_get_changed_files_strips_blank_lines():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="\nfoo.cpp\n\nbar.h\n")
        files = get_changed_files("main")
    assert files == ["foo.cpp", "bar.h"]


# ── _cmd_review_diff ───────────────────────────────────────────────────────────

class _Args:
    def __init__(self, **kw):
        self.base = kw.get("base", "main")
        self.head = kw.get("head", "HEAD")
        self.result = kw.get("result", "Saved/AutomationReports/result.json")
        self.out = kw.get("out", None)
        self.out_md = kw.get("out_md", None)


def test_cmd_review_diff_writes_result_json(tmp_path):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.review.get_changed_files") as mock_git:
        mock_git.return_value = ["Content/Foo.uasset", "Source/Bar.cpp"]
        ret = _cmd_review_diff(_Args(result=str(result_path)))
    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True
    assert data["action"] == "diff"


def test_cmd_review_diff_risk_classification(tmp_path):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.review.get_changed_files") as mock_git:
        mock_git.return_value = ["Content/Foo.uasset", "Source/Bar.cpp", "README.md"]
        _cmd_review_diff(_Args(result=str(result_path)))
    data = json.loads(result_path.read_text())
    assert len(data["risk"]["high"]) == 1
    assert len(data["risk"]["medium"]) == 1
    assert len(data["risk"]["low"]) == 1


def test_cmd_review_diff_writes_markdown(tmp_path):
    result_path = tmp_path / "result.json"
    out_path = tmp_path / "risk.diff.md"
    with patch("ue_auto.commands.review.get_changed_files") as mock_git:
        mock_git.return_value = ["Content/Foo.uasset", "Source/Bar.cpp"]
        _cmd_review_diff(_Args(result=str(result_path), out=str(out_path)))
    assert out_path.exists()
    content = out_path.read_text()
    assert "HIGH" in content
    assert "Foo.uasset" in content


def test_cmd_review_diff_no_changes(tmp_path):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.review.get_changed_files") as mock_git:
        mock_git.return_value = []
        ret = _cmd_review_diff(_Args(result=str(result_path)))
    assert ret == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_cmd_review_diff_git_error(tmp_path):
    result_path = tmp_path / "result.json"
    with patch("ue_auto.commands.review.get_changed_files") as mock_git:
        mock_git.side_effect = subprocess.CalledProcessError(128, "git")
        ret = _cmd_review_diff(_Args(result=str(result_path)))
    assert ret == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
