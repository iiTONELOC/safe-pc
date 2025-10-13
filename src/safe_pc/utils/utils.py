import asyncio
import collections.abc
from os import getenv
from typing import Any
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from socket import gethostname, gethostbyname


def get_local_ip() -> str:
    """Gets the local IP address of the machine.

    Returns:
        str: The local IP address.
    """
    hostname = gethostname()
    local_ip = gethostbyname(hostname)
    return local_ip



def handle_keyboard_interrupt(func:collections.abc.Callable[..., Any]) -> collections.abc.Callable[..., Any]:
    """Decorator to handle KeyboardInterrupt exceptions gracefully.

    Args:
        func (callable): The function to be decorated.

    Returns:
        callable: The wrapped function with KeyboardInterrupt handling.

    Usage:
    ```python
        @handle_keyboard_interrupt
        def main():
            # do some stuff
            print("Running...")
    ```
    """

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except KeyboardInterrupt:
            print("Operation cancelled by user.")
            exit(0)

    return wrapper


def IS_TESTING() -> bool:
    """Check if the code is running in a testing environment.

    Returns:
        bool: True if running tests, False otherwise.
    """
    return getenv("CAPSTONE_TESTING", "0") == "1"


def IS_VERBOSE() -> bool:
    """Check if verbose mode is enabled via command-line arguments.

    Returns:
        bool: True if verbose mode is enabled, False otherwise.
    """
    return getenv("CAPSTONE_VERBOSE", "0") == "1"


def calculate_percentage(part: int, whole: int) -> int:
    """Calculate the percentage of `part` with respect to `whole`.

    Args:
        part (int): The part value.
        whole (int): The whole value.

    Returns:
        float: The calculated percentage. Returns 0.0 if `whole` is 0 to avoid division by zero.
    """
    if whole == 0:
        return 0
    return ((part / whole) * 100).__round__(0).__int__()



@dataclass
class CmdResult:
    stdout: str
    stderr: str
    returncode: int|None


class CommandError(RuntimeError):
    def __init__(self, args: Sequence[str], rc: int|None, stdout: str, stderr: str):
        super().__init__(f"Command failed ({rc}): {' '.join(map(str, args))}")
        self.args_list = list(args)
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


async def run_command_async(
    *args: str | Path,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> CmdResult:
    cmd = tuple(str(a) for a in args)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await proc.communicate()
    except (asyncio.CancelledError, asyncio.TimeoutError):
        proc.kill()
        await proc.communicate()
        raise
    rc = proc.returncode
    stdout = stdout_b.decode(errors="replace")
    stderr = stderr_b.decode(errors="replace")
    if check and rc != 0:
        raise CommandError(cmd, rc, stdout, stderr)
    return CmdResult(stdout, stderr, rc)