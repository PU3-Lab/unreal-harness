"""Tests for argparse option propagation through nested subparsers."""
import sys
import pytest
from unittest.mock import patch


def test_project_at_root_level_reaches_ping():
    """--project before domain subcommand must reach the ping handler's args.project."""
    captured = {}

    def mock_ping(args):
        captured["project"] = getattr(args, "project", None)
        return 0

    with patch("ue_auto.commands.ai_statetree._cmd_ping", mock_ping), patch.object(
        sys,
        "argv",
        ["ue-auto", "--project", "Game.uproject", "ai", "statetree", "ping"],
    ):
        with pytest.raises(SystemExit):
            from ue_auto.main import main

            main()

    assert captured.get("project") == "Game.uproject"


def test_project_after_ping_subcommand_reaches_ping():
    """--project after the leaf subcommand must also reach args.project."""
    captured = {}

    def mock_ping(args):
        captured["project"] = getattr(args, "project", None)
        return 0

    with patch("ue_auto.commands.ai_statetree._cmd_ping", mock_ping), patch.object(
        sys,
        "argv",
        ["ue-auto", "ai", "statetree", "ping", "--project", "Game.uproject"],
    ):
        with pytest.raises(SystemExit):
            from ue_auto.main import main

            main()

    assert captured.get("project") == "Game.uproject"


def test_result_path_overridden_at_root_reaches_ping():
    """--result set at root level must not be reset to default by leaf parser."""
    captured = {}

    def mock_ping(args):
        captured["result"] = getattr(args, "result", None)
        return 0

    with patch("ue_auto.commands.ai_statetree._cmd_ping", mock_ping), patch.object(
        sys,
        "argv",
        [
            "ue-auto",
            "--result",
            "/tmp/my_result.json",
            "ai",
            "statetree",
            "ping",
        ],
    ):
        with pytest.raises(SystemExit):
            from ue_auto.main import main

            main()

    assert captured.get("result") == "/tmp/my_result.json"
