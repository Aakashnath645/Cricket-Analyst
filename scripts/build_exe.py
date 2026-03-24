from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CricAnalyst desktop executable with PyInstaller.")
    parser.add_argument("--name", type=str, default="CricAnalyst")
    parser.add_argument("--onefile", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--windowed", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--entry", type=str, default="run_desktop.py")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    entry_file = root / args.entry
    icon_file = root / "assets" / "icon.ico"
    if not entry_file.exists():
        print(f"Entry file not found: {entry_file}")
        return 1

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        args.name,
    ]
    if args.onefile:
        command.append("--onefile")
    if args.windowed:
        command.append("--windowed")
    if icon_file.exists():
        command.extend(["--icon", str(icon_file)])

    models_dir = root / "models"
    data_dir = root / "data"
    if models_dir.exists():
        command.extend(["--add-data", f"{models_dir};models"])
    if data_dir.exists():
        command.extend(["--add-data", f"{data_dir};data"])

    command.append(str(entry_file))
    print("Running:", " ".join(command))
    subprocess.run(command, cwd=root, check=True)

    dist_path = root / "dist"
    print(f"\nBuild complete. Output in: {dist_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
