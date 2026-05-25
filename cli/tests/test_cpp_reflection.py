"""Tests for ue-auto cpp validate-reflection (TDD — RED first)."""
import json
import textwrap
import pytest
from pathlib import Path

from ue_auto.commands.cpp_cmd import parse_reflection_macros, validate_reflection_issues


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_header(path: Path, content: str) -> Path:
    path.write_text(content)
    return path


_GOOD_HEADER = textwrap.dedent("""\
    #pragma once
    #include "CoreMinimal.h"
    #include "MyComp.generated.h"

    UCLASS()
    class UMyComp : public UActorComponent
    {
        GENERATED_BODY()
    public:
        UPROPERTY(EditAnywhere, BlueprintReadOnly, Category = "Stats")
        float MaxHealth;

        UFUNCTION(BlueprintCallable, Category = "Stats")
        void ApplyDamage(float Amount);
    };
""")

_BAD_HEADER_NO_CATEGORY = textwrap.dedent("""\
    #pragma once
    #include "CoreMinimal.h"
    #include "MyBadComp.generated.h"

    UCLASS()
    class UMyBadComp : public UActorComponent
    {
        GENERATED_BODY()
    public:
        UFUNCTION(BlueprintCallable)
        void BadFunc();

        UFUNCTION(BlueprintNativeEvent)
        void AlsoBad();
    };
""")


# ── parse_reflection_macros ───────────────────────────────────────────────────

def test_parse_reflection_finds_ufunction(tmp_path):
    h = _write_header(tmp_path / "MyComp.h", _GOOD_HEADER)
    items = parse_reflection_macros(str(tmp_path))
    fns = [i for i in items if i["macro"] == "UFUNCTION"]
    assert len(fns) >= 1
    assert any(i["name"] == "ApplyDamage" for i in fns)


def test_parse_reflection_finds_uproperty(tmp_path):
    h = _write_header(tmp_path / "MyComp.h", _GOOD_HEADER)
    items = parse_reflection_macros(str(tmp_path))
    props = [i for i in items if i["macro"] == "UPROPERTY"]
    assert len(props) >= 1
    assert any(i["name"] == "MaxHealth" for i in props)


def test_parse_reflection_records_file_path(tmp_path):
    h = _write_header(tmp_path / "MyComp.h", _GOOD_HEADER)
    items = parse_reflection_macros(str(tmp_path))
    assert all("file" in i for i in items)
    assert all("MyComp.h" in i["file"] for i in items)


def test_parse_reflection_records_macro_args(tmp_path):
    h = _write_header(tmp_path / "MyComp.h", _GOOD_HEADER)
    items = parse_reflection_macros(str(tmp_path))
    fn = next(i for i in items if i.get("name") == "ApplyDamage")
    assert "BlueprintCallable" in fn["args"]


def test_parse_reflection_scans_multiple_headers(tmp_path):
    _write_header(tmp_path / "A.h", _GOOD_HEADER)
    _write_header(tmp_path / "B.h", _BAD_HEADER_NO_CATEGORY)
    items = parse_reflection_macros(str(tmp_path))
    files = {i["file"] for i in items}
    assert any("A.h" in f for f in files)
    assert any("B.h" in f for f in files)


def test_parse_reflection_finds_ufunction_with_meta_nested_parens(tmp_path):
    content = textwrap.dedent("""\
        #pragma once
        #include "CoreMinimal.h"
        #include "MyComp.generated.h"

        UCLASS()
        class UMyComp : public UActorComponent
        {
            GENERATED_BODY()
        public:
            UFUNCTION(BlueprintCallable, Category = "Stats", Meta = (DisplayName = "Apply Damage"))
            void ApplyDamageWithMeta(float Amount);
        };
    """)
    _write_header(tmp_path / "MyComp.h", content)
    items = parse_reflection_macros(str(tmp_path))
    fns = [i for i in items if i["macro"] == "UFUNCTION"]
    assert any(i["name"] == "ApplyDamageWithMeta" for i in fns)


def test_parse_reflection_empty_directory(tmp_path):
    items = parse_reflection_macros(str(tmp_path))
    assert items == []


def test_parse_reflection_skips_non_header_files(tmp_path):
    (tmp_path / "MyComp.cpp").write_text('#include "MyComp.h"\nvoid Foo() {}')
    items = parse_reflection_macros(str(tmp_path))
    assert items == []


# ── validate_reflection_issues ────────────────────────────────────────────────

def test_validate_reflection_no_issues_when_all_have_category():
    items = [
        {"macro": "UFUNCTION", "args": "BlueprintCallable, Category = \"Stats\"",
         "name": "ApplyDamage", "file": "MyComp.h", "line": 10},
    ]
    policy = {"functions": {"require_category": True}}
    issues = validate_reflection_issues(items, policy)
    assert issues == []


def test_validate_reflection_missing_category_on_blueprintcallable():
    items = [
        {"macro": "UFUNCTION", "args": "BlueprintCallable",
         "name": "BadFunc", "file": "MyBadComp.h", "line": 8},
    ]
    policy = {"functions": {"require_category": True}}
    issues = validate_reflection_issues(items, policy)
    codes = [i["code"] for i in issues]
    assert "MISSING_CATEGORY" in codes


def test_validate_reflection_missing_category_on_blueprintnativeevent():
    items = [
        {"macro": "UFUNCTION", "args": "BlueprintNativeEvent",
         "name": "AlsoBad", "file": "MyBadComp.h", "line": 11},
    ]
    policy = {"functions": {"require_category": True}}
    issues = validate_reflection_issues(items, policy)
    codes = [i["code"] for i in issues]
    assert "MISSING_CATEGORY" in codes


def test_validate_reflection_uproperty_not_checked_for_category_when_not_in_policy():
    items = [
        {"macro": "UPROPERTY", "args": "EditAnywhere", "name": "Score",
         "file": "MyComp.h", "line": 5},
    ]
    policy = {"functions": {"require_category": True}}
    issues = validate_reflection_issues(items, policy)
    assert issues == []


def test_validate_reflection_non_blueprint_function_skips_category_check():
    items = [
        {"macro": "UFUNCTION", "args": "NetMulticast, Reliable",
         "name": "RpcFunc", "file": "MyComp.h", "line": 5},
    ]
    policy = {"functions": {"require_category": True}}
    issues = validate_reflection_issues(items, policy)
    assert issues == []


def test_validate_reflection_returns_file_and_line_in_issue():
    items = [
        {"macro": "UFUNCTION", "args": "BlueprintCallable",
         "name": "BadFunc", "file": "MyBadComp.h", "line": 8},
    ]
    policy = {"functions": {"require_category": True}}
    issues = validate_reflection_issues(items, policy)
    assert len(issues) == 1
    assert issues[0]["file"] == "MyBadComp.h"
    assert issues[0]["line"] == 8


def test_validate_reflection_policy_disabled_skips_check():
    items = [
        {"macro": "UFUNCTION", "args": "BlueprintCallable",
         "name": "BadFunc", "file": "MyBadComp.h", "line": 8},
    ]
    policy = {"functions": {"require_category": False}}
    issues = validate_reflection_issues(items, policy)
    assert issues == []


# ── CLI integration ───────────────────────────────────────────────────────────

def test_cmd_validate_reflection_missing_source_returns_1(tmp_path):
    import subprocess, sys
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-reflection",
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False


def test_cmd_validate_reflection_clean_source_returns_0(tmp_path):
    import subprocess, sys
    _write_header(tmp_path / "Good.h", _GOOD_HEADER)
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("functions:\n  require_category: true\n")
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-reflection",
         "--source", str(tmp_path),
         "--policy", str(policy_path),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 0
    data = json.loads(result_path.read_text())
    assert data["ok"] is True


def test_cmd_validate_reflection_violations_returns_1(tmp_path):
    import subprocess, sys
    _write_header(tmp_path / "Bad.h", _BAD_HEADER_NO_CATEGORY)
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("functions:\n  require_category: true\n")
    result_path = tmp_path / "result.json"
    ret = subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-reflection",
         "--source", str(tmp_path),
         "--policy", str(policy_path),
         "--result", str(result_path)],
        capture_output=True, text=True,
    )
    assert ret.returncode == 1
    data = json.loads(result_path.read_text())
    assert data["ok"] is False
    assert len(data["checks"]) >= 2


def test_cmd_validate_reflection_result_contains_checks(tmp_path):
    import subprocess, sys
    _write_header(tmp_path / "Good.h", _GOOD_HEADER)
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("functions:\n  require_category: true\n")
    result_path = tmp_path / "result.json"
    subprocess.run(
        [sys.executable, "-m", "ue_auto", "cpp", "validate-reflection",
         "--source", str(tmp_path),
         "--policy", str(policy_path),
         "--result", str(result_path)],
        capture_output=True,
    )
    data = json.loads(result_path.read_text())
    assert "checks" in data
