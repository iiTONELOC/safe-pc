"""
This script runs the A development server with live-reloading using nodemon.
"""

from pathlib import Path
from sys import platform, exit
from subprocess import run, CalledProcessError
from safe_pc.utils import handle_keyboard_interrupt


@handle_keyboard_interrupt
def main():
    cmd = ["npm", "run", "dev"]
    TAILWIND_DIR = Path(__file__).resolve().parent / ".." / "front_end" / "tailwindcss"

    # On Windows, the npm command is really npm.cmd and might fail otherwise
    if platform == "win32":
        cmd[0] = "npm.cmd"

    try:
        run(args=cmd, cwd=TAILWIND_DIR, check=True)
    except CalledProcessError as e:
        print(f"Error running dev server: {e}")
        exit(code=1)


if __name__ == "__main__":
    main()
