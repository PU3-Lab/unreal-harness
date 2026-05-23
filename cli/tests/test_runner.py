"""Tests for runner.py subprocess error handling."""
import os
import subprocess
import pytest
from unittest.mock import patch

from ue_auto.runner import RunnerError, run_commandlet


def test_file_not_found_becomes_runner_error(tmp_path):
    """FileNotFoundError from subprocess must be wrapped as RunnerError, not crash."""
    uproject = str(tmp_path / "Test.uproject")

    with patch.dict(os.environ, {"UE_EDITOR_CMD": "/nonexistent/UnrealEditor-Cmd"}), \
         patch("subprocess.run", side_effect=FileNotFoundError("No such file")):
        with pytest.raises(RunnerError, match="No such file"):
            run_commandlet(uproject, "UEAutoPingCommandlet")


def test_timeout_becomes_runner_error(tmp_path):
    """TimeoutExpired from subprocess must be wrapped as RunnerError, not crash."""
    uproject = str(tmp_path / "Test.uproject")

    with patch.dict(os.environ, {"UE_EDITOR_CMD": "/fake/editor"}), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="editor", timeout=60)):
        with pytest.raises(RunnerError, match="timed out"):
            run_commandlet(uproject, "UEAutoPingCommandlet", timeout=60)


def test_find_editor_reads_ue_editor_cmd_env_var():
    """UE_EDITOR_CMD env var must be returned by find_editor()."""
    from ue_auto.runner import find_editor

    with patch.dict(os.environ, {"UE_EDITOR_CMD": "/custom/path/UnrealEditor-Cmd"}):
        assert find_editor() == "/custom/path/UnrealEditor-Cmd"
