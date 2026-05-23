import os
import subprocess
import sys
from pathlib import Path


_KNOWN_EDITOR_PATHS = {
    "darwin": [
        "/Users/Shared/Epic Games/UE_5.7/Engine/Binaries/Mac/UnrealEditor-Cmd",
        "/Users/Shared/Epic Games/UE_5.5/Engine/Binaries/Mac/UnrealEditor-Cmd",
        "/Applications/Epic Games/UE_5.5/Engine/Binaries/Mac/UnrealEditor-Cmd",
        "/Applications/Epic Games/UE_5.4/Engine/Binaries/Mac/UnrealEditor-Cmd",
        "/Applications/Epic Games/UE_5.3/Engine/Binaries/Mac/UnrealEditor-Cmd",
    ],
    "win32": [
        r"C:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
        r"C:\Program Files\Epic Games\UE_5.4\Engine\Binaries\Win64\UnrealEditor-Cmd.exe",
    ],
    "linux": [
        "/opt/unreal/UE_5.5/Engine/Binaries/Linux/UnrealEditor-Cmd",
    ],
}


def find_editor() -> str | None:
    if env := os.environ.get("UE_EDITOR_CMD"):
        return env
    for candidate in _KNOWN_EDITOR_PATHS.get(sys.platform, []):
        if Path(candidate).exists():
            return candidate
    return None


class RunnerError(RuntimeError):
    pass


def run_commandlet(
    project: str,
    commandlet: str,
    extra_args: list[str] | None = None,
    *,
    timeout: int = 120,
) -> int:
    editor = find_editor()
    if editor is None:
        raise RunnerError(
            "UnrealEditor-Cmd not found. "
            "Set UE_EDITOR_CMD env var or install UE 5.3~5.5 in the standard path."
        )

    cmd = [
        editor,
        str(Path(project).resolve()),
        f"-run={commandlet}",
        "-unattended",
        "-nop4",
        "-nosplash",
    ]
    if extra_args:
        cmd += extra_args

    try:
        result = subprocess.run(cmd, timeout=timeout)
        return result.returncode
    except FileNotFoundError as e:
        raise RunnerError(str(e)) from e
    except subprocess.TimeoutExpired:
        raise RunnerError(f"UnrealEditor-Cmd timed out after {timeout}s") from None
