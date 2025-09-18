#!/usr/bin/env python3
import sys
import argparse
import subprocess
from pathlib import Path

VENV = Path(".venv")
BIN = VENV / "bin"
TASKS = {
    "install-dev": f"{BIN}/pip install -e '.[dev]'",
    "install": f"{BIN}/pip install -e .",
    "test": f"{BIN}/pytest --cov=capstone tests/",
    "test-coverage": f"{BIN}/pytest --cov=capstone tests/ --cov-report=html",
    "lint": f"{BIN}/black .",
    "docs-dev": f"{BIN}/mkdocs serve",
    "docs-build": f"{BIN}/mkdocs build",
    "docs-deploy": f"{BIN}/mkdocs gh-deploy",
    "prox-dl-iso": f"{BIN}/python -m capstone.proxmox.iso.downloader",
}


def _ensure_venv():
    if not VENV.exists():
        print("Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
        subprocess.check_call(
            [
                str(BIN / "python"),
                "-m",
                "pip",
                "install",
                "--upgrade",
                "pip",
                "setuptools",
                "wheel",
            ]
        )


def _run(cmd: str):
    print(f"Running: {cmd}\n")
    return subprocess.call(cmd, shell=True, executable="/bin/bash")


def main():
    """
    Parses command-line arguments to select and run a specified task.

    The idea is like npm scripts, you can run them with `cap <task>` from the command
    line, after installation.

    To run directly without installation, use `python3 -m capstone.scripts <task>`.

    Raises:
        SystemExit: If the specified task is not found or after running the task.
    """

    parser = argparse.ArgumentParser(description="Task runner (npm style)")
    parser.add_argument("task", help="Task to run")
    args = parser.parse_args()

    _ensure_venv()

    task = args.task
    if task not in TASKS:
        print(f"Unknown task: {task}")
        print("Available tasks:", ", ".join(TASKS.keys()))
        sys.exit(1)

    sys.exit(_run(TASKS[task]))


if __name__ == "__main__":
    main()
