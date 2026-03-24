from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    run_backend = root / "run_backend.py"
    icon_file = root / "assets" / "icon.ico"
    if not run_backend.exists():
        print(f"Missing backend entry: {run_backend}")
        return 1

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "CricAnalystApi",
        "--onefile",
        "--paths",
        str(root),
        "--hidden-import",
        "backend",
        "--hidden-import",
        "backend.server",
        "--collect-submodules",
        "backend",
        "--collect-submodules",
        "sklearn",
        "--collect-submodules",
        "scipy",
        str(run_backend),
    ]
    if icon_file.exists():
        command[4:4] = ["--icon", str(icon_file)]
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=root, check=True)
    print("Backend executable ready in dist/CricAnalystApi.exe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
