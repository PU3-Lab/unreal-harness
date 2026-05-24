import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

from ue_auto import report as report_mod
from ue_auto import result as result_mod


def find_build_script() -> str | None:
    if script := os.environ.get("UE_BUILD_SCRIPT"):
        return script

    editor_cmd = os.environ.get("UE_EDITOR_CMD")
    if editor_cmd:
        # UnrealEditor-Cmd lives at Engine/Binaries/<Platform>/
        # Build script lives at Engine/Build/BatchFiles/Build.{sh,bat}
        engine_dir = Path(editor_cmd).parent.parent.parent  # Engine/
        ext = "bat" if sys.platform == "win32" else "sh"
        candidate = engine_dir / "Build" / "BatchFiles" / f"Build.{ext}"
        if candidate.exists():
            return str(candidate)

    return None


def _editor_target(project: str) -> str:
    name = Path(project).stem
    return f"{name}Editor"


def _build_platform() -> str:
    if sys.platform == "darwin":
        return "Mac"
    if sys.platform == "win32":
        return "Win64"
    return "Linux"


def register(
    sub: argparse.ArgumentParser,
    add_common: Callable[[argparse.ArgumentParser], None],
) -> None:
    p = sub.add_parser("editor", help="Build the UE editor target via UBT")
    add_common(p)
    p.add_argument("--config", metavar="CONFIG", default="Development",
                   help="Build configuration (default: Development)")
    p.set_defaults(func=_cmd_build_editor)


def _cmd_build_editor(args) -> int:
    project = getattr(args, "project", None)
    if not project:
        r = result_mod.failure("build", "MISSING_PROJECT", "--project is required",
                               hint="Pass --project path/to/MyGame.uproject")
        result_mod.write(r, args.result)
        return 1

    build_script = find_build_script()
    if not build_script:
        r = result_mod.failure(
            "build", "BUILD_SCRIPT_NOT_FOUND",
            "UnrealBuildTool script not found",
            hint="Set UE_BUILD_SCRIPT env var or UE_EDITOR_CMD pointing to the engine.",
        )
        result_mod.write(r, args.result)
        return 1

    target = _editor_target(project)
    platform = _build_platform()
    config = getattr(args, "config", "Development") or "Development"

    cmd = [build_script, target, platform, config, str(Path(project).resolve())]
    if sys.platform == "win32" and build_script.lower().endswith(".bat"):
        cmd = ["cmd.exe", "/c"] + cmd

    proc = subprocess.run(cmd)
    ok = proc.returncode == 0

    if ok:
        r = result_mod.success("build", f"Build succeeded: {target} {platform} {config}")
    else:
        r = result_mod.failure(
            "build", "BUILD_FAILED",
            f"Build failed with exit code {proc.returncode}",
            hint="Check the build log for compile/link errors.",
        )

    result_mod.write(r, args.result)

    status = "PASS" if ok else "FAIL"
    out = getattr(args, "out", None)
    if out:
        rpt = (
            report_mod.ReportBuilder("build editor", "build")
            .status(status)
            .add_section("Summary", [
                f"- Target: `{target}`",
                f"- Platform: `{platform}`",
                f"- Config: `{config}`",
                f"- Exit code: `{proc.returncode}`",
            ])
            .build()
        )
        report_mod.write(rpt, out)

    print(f"{status}  ue-auto build editor  ({target} {platform} {config})")
    return 0 if ok else 1
