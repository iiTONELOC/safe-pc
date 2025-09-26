"""
This script builds the Tailwind CSS files using the Tailwind CLI via npm.
It can be run in two modes: production (default) and development (with 'dev' argument).

Note: this requires that Node.js and npm are installed on the system, but is only required for development.
"""

from pathlib import Path
from sys import platform, argv, exit
from subprocess import run, CalledProcessError

cmd = ["npm", "run", "build"]
TAILWIND_DIR = Path(__file__).resolve().parent / ".." / "front_end" / "tailwindcss"


def build_css(args=None):
    args = args or argv

    # On Windows, the npm command is really npm.cmd and might fail otherwise
    if platform == "win32":
        cmd[0] = "npm.cmd"

    # If requesting dev mode, change the command to build:dev
    if len(args) > 1 and args[1] == "dev":
        cmd[-1] = "build:dev"

    try:
        run(args=cmd, cwd=TAILWIND_DIR, check=True)
    except CalledProcessError as e:
        print(f"Error building CSS: {e}")
        exit(code=1)


if __name__ == "__main__":

    build_css(argv)
