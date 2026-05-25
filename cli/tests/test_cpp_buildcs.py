"""Tests for ue-auto cpp validate-buildcs (TDD — RED first)."""
import json
import textwrap
import pytest
from pathlib import Path

from ue_auto.commands.cpp_cmd import parse_buildcs, validate_buildcs_issues


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_buildcs(path: Path, public: list[str], private: list[str]) -> Path:
    pub_str = ", ".join(f'"{m}"' for m in public)
    priv_str = ", ".join(f'"{m}"' for m in private)
    content = textwrap.dedent(f"""\
        using UnrealBuildTool;

        public class MyGame : ModuleRules
        {{
            public MyGame(ReadOnlyTargetRules Target) : base(Target)
            {{
                PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

                PublicDependencyModuleNames.AddRange(new string[] {{ {pub_str} }});

                PrivateDependencyModuleNames.AddRange(new string[] {{ {priv_str} }});
            }}
        }}
    """)
    path.write_text(content)
    return path


# ── parse_buildcs ─────────────────────────────────────────────────────────────

def test_parse_buildcs_extracts_public_deps(tmp_path):
    f = _write_buildcs(tmp_path / "MyGame.Build.cs", ["Core", "CoreUObject", "Engine"], ["GameplayTags"])
    result = parse_buildcs(str(f))
    assert "Core" in result["public"]
    assert "CoreUObject" in result["public"]
    assert "Engine" in result["public"]


def test_parse_buildcs_extracts_private_deps(tmp_path):
    f = _write_buildcs(tmp_path / "MyGame.Build.cs", ["Core"], ["GameplayTags", "AIModule"])
    result = parse_buildcs(str(f))
    assert "GameplayTags" in result["private"]
    assert "AIModule" in result["private"]


def test_parse_buildcs_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_buildcs(str(tmp_path / "Missing.Build.cs"))


def test_parse_buildcs_empty_lists(tmp_path):
    content = textwrap.dedent("""\
        using UnrealBuildTool;
        public class Foo : ModuleRules {
            public Foo(ReadOnlyTargetRules Target) : base(Target) {}
        }
    """)
    f = tmp_path / "Foo.Build.cs"
    f.write_text(content)
    result = parse_buildcs(str(f))
    assert result["public"] == []
    assert result["private"] == []


def test_parse_buildcs_multiline_addrange(tmp_path):
    content = textwrap.dedent("""\
        using UnrealBuildTool;
        public class Bar : ModuleRules {
            public Bar(ReadOnlyTargetRules Target) : base(Target) {
                PublicDependencyModuleNames.AddRange(new string[] {
                    "Core",
                    "CoreUObject",
                    "Engine"
                });
            }
        }
    """)
    f = tmp_path / "Bar.Build.cs"
    f.write_text(content)
    result = parse_buildcs(str(f))
    assert "Core" in result["public"]
    assert "Engine" in result["public"]


def test_parse_buildcs_comment_with_brace_does_not_break_parsing(tmp_path):
    content = textwrap.dedent("""\
        using UnrealBuildTool;
        public class MyGame : ModuleRules {
            public MyGame(ReadOnlyTargetRules Target) : base(Target) {
                PublicDependencyModuleNames.AddRange(new string[] {
                    "Core",       // Note: {essential}
                    "Engine"
                });
            }
        }
    """)
    f = tmp_path / "MyGame.Build.cs"
    f.write_text(content)
    result = parse_buildcs(str(f))
    assert "Core" in result["public"]
    assert "Engine" in result["public"]


def test_parse_buildcs_add_single_module(tmp_path):
    content = textwrap.dedent("""\
        using UnrealBuildTool;
        public class Baz : ModuleRules {
            public Baz(ReadOnlyTargetRules Target) : base(Target) {
                PublicDependencyModuleNames.Add("Core");
                PrivateDependencyModuleNames.Add("AIModule");
            }
        }
    """)
    f = tmp_path / "Baz.Build.cs"
    f.write_text(content)
    result = parse_buildcs(str(f))
    assert "Core" in result["public"]
    assert "AIModule" in result["private"]


# ── validate_buildcs_issues ───────────────────────────────────────────────────

def test_validate_buildcs_no_issues_when_clean():
    deps = {"public": ["Core", "CoreUObject", "Engine"], "private": ["AIModule"]}
    issues = validate_buildcs_issues(deps)
    assert issues == []


def test_validate_buildcs_finds_duplicate_across_public_private():
    deps = {"public": ["Core", "GameplayTags"], "private": ["AIModule", "GameplayTags"]}
    issues = validate_buildcs_issues(deps)
    codes = [i["code"] for i in issues]
    assert "DUPLICATE_DEPENDENCY" in codes
    dup = next(i for i in issues if i["code"] == "DUPLICATE_DEPENDENCY")
    assert "GameplayTags" in dup["message"]


def test_validate_buildcs_finds_missing_core():
    deps = {"public": ["Engine"], "private": []}
    issues = validate_buildcs_issues(deps)
    codes = [i["code"] for i in issues]
    assert "MISSING_CORE" in codes


def test_validate_buildcs_no_missing_core_when_present():
    deps = {"public": ["Core", "CoreUObject", "Engine"], "private": []}
    issues = validate_buildcs_issues(deps)
    codes = [i["code"] for i in issues]
    assert "MISSING_CORE" not in codes


# ── CLI integration ───────────────────────────────────────────────────────────

def test_cmd_validate_buildcs_missing_buildcs_arg_returns_1(tmp_path):
    import subprocess, sys
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-buildcs",
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_validate_buildcs_nonexistent_file_returns_1(tmp_path):
    import subprocess, sys
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-buildcs",
         "--buildcs", str(tmp_path / "Missing.Build.cs"),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_validate_buildcs_clean_file_returns_0(tmp_path):
    import subprocess, sys
    buildcs = _write_buildcs(tmp_path / "MyGame.Build.cs", ["Core", "CoreUObject", "Engine"], ["AIModule"])
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-buildcs",
         "--buildcs", str(buildcs),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_cmd_validate_buildcs_result_contains_checks(tmp_path):
    import subprocess, sys
    buildcs = _write_buildcs(tmp_path / "MyGame.Build.cs", ["Core", "CoreUObject", "Engine"], ["AIModule"])
    result_path = tmp_path / "result.json"
    subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-buildcs",
         "--buildcs", str(buildcs),
         "--result", str(result_path)],
        capture_output=True,
    )
    data = json.loads(result_path.read_text())
    assert "checks" in data
    assert isinstance(data["checks"], list)


def test_cmd_validate_buildcs_duplicate_dep_reports_issue(tmp_path):
    import subprocess, sys
    buildcs = _write_buildcs(
        tmp_path / "MyGame.Build.cs",
        ["Core", "CoreUObject", "Engine", "GameplayTags"],
        ["AIModule", "GameplayTags"],
    )
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-buildcs",
         "--buildcs", str(buildcs),
         "--result", str(result_path)],
        capture_output=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    codes = [c["code"] for c in data["checks"]]
    assert "DUPLICATE_DEPENDENCY" in codes
