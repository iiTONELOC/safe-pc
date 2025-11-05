import bz2
import asyncio
from typing import Any
from pathlib import Path
from time import monotonic
from logging import getLogger
from httpx import AsyncClient
from os import environ, write
from re import compile as re_compile
from collections.abc import Callable
from logging import Logger, getLogger, INFO
from socket import gethostname, gethostbyname

import pexpect


LOGGER = getLogger(__name__)
BUFFER = 2048


class PexpectLogger:
    def __init__(self, logger: Logger, level: int = INFO, prefix: str = "", flush_interval: float = 0.75):
        self.logger = logger
        self.level = level
        self.prefix = prefix
        self.buffer = ""
        self.last_flush = monotonic()
        self.flush_interval = flush_interval

    def write(self, message: str):
        if not message:
            return
        now = monotonic()
        message = message.replace("\r", "")
        self.buffer += message

        # Flush full lines immediately
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                self.logger.log(self.level, f"{self.prefix}{line.rstrip()}")
            self.last_flush = now

        # Flush incomplete line if stale or too long
        if (len(self.buffer) >= BUFFER or now - self.last_flush > self.flush_interval) and self.buffer.strip():
            self.logger.log(self.level, f"{self.prefix}{self.buffer.rstrip()}")
            self.buffer = ""
            self.last_flush = now

    def flush(self):
        # Do nothing — pexpect flushes after each byte
        return


def send_key_to_pexpect_proc(key: str, child) -> None:  # type: ignore
    """Send a keypress to a pexpect child process.
    Args:
        key (str): The key to send. Supported keys: up, down, right,
            left, tab, enter, ctrl_c, ctrl_O.
        child: The pexpect child process.
    """
    keys = {
        "up": b"\x1b[A",
        "down": b"\x1b[B",
        "right": b"\x1b[C",
        "left": b"\x1b[D",
        "tab": b"\t",
        "enter": b"\r",
        "ctrl_c": b"\x03",
        "ctrl_O": b"\x0f",
    }
    write(child.child_fd, keys[key])  # type: ignore


def pexpect_connect_to_serial_socket(socket_path: str, logger: Logger, prefix: str = "") -> pexpect.spawn:  # type: ignore
    """Connect to a VM's serial socket using pexpect and socat. Returns the pexpect spawn object.
    Args:
        socket_path (str): The path to the VM's serial socket.
        logger (Logger): The logger to use for logging output.
        prefix (str): Optional prefix for log messages.
    Returns:
        pexpect.spawn: The pexpect spawn object connected to the serial socket.
    """
    environ["TERM"] = "vt100"  # set terminal type for pexpect/socat

    # originally tried using qm terminal, but either pexpect or qm terminal was removing control characters
    # decided to connect to the socket directly using socat instead, any control characters are sent using the
    # send_key_to_pexpect_proc function above. It uses os.write to write directly to the child_fd (the unix socket),
    # bypassing pexpect's send method and enabling the raw bytes to be sent as-is

    child = pexpect.spawn(  # type: ignore
        f"socat -,raw,echo=0 UNIX-CONNECT:{socket_path}",
        encoding="utf-8",
        timeout=600,
        dimensions=(24, 80),
    )

    child.delaybeforesend = 0.1
    child.logfile_read = PexpectLogger(logger, prefix=prefix + "[VM Output] ")
    child.logfile_send = PexpectLogger(logger, prefix=prefix + "[VM Input] ")

    return child  # type: ignore


def strip_ansi_escape_sequences(text: str) -> str:
    """Strip ANSI escape sequences from a given text.

    Args:
        text (str): The input text containing ANSI escape sequences.
    Returns:
        str: The text with ANSI escape sequences removed.
    """

    ansi_escape = re_compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", text)


def get_local_ip() -> str:
    """Gets the local IP address of the machine.

    Returns:
        str: The local IP address.
    """
    env_ip = environ.get("HOST_IP")
    if env_ip and env_ip.strip() != "":
        return env_ip
    hostname = gethostname()
    local_ip = gethostbyname(hostname)
    return local_ip


def handle_keyboard_interrupt(
    func: Callable[..., Any],
) -> Callable[..., Any]:
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


async def fetch_text_from_url(url: str) -> str:
    """Fetch text content from a URL asynchronously.

    Args:
        url (str): The URL to fetch content from.

    Returns:
        str: The text content retrieved from the URL. Returns an empty string on failure.
    """

    try:
        async with AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text if response else ""
    except Exception as e:

        LOGGER.error(f"Failed to fetch text from {url}: {e}")
        return ""


async def remove_bz2_compression(iso_path: Path) -> Path:
    """Remove compression from a file

    Args:
        iso_path (Path): The path to the compressed file.

    Raises:
        ValueError: if the file is not a .bz2 compressed file.
        FileNotFoundError: if the file does not exist.

    Returns:
        Path: The path to the decompressed file.
    """

    # ensure the file exists
    if not iso_path.exists():
        raise FileNotFoundError(f"File not found: {iso_path}")

    # remove the extension
    if iso_path.suffix != ".bz2":
        raise ValueError("File is not a .bz2 compressed file")

    loop = asyncio.get_running_loop()
    decompressed_path = iso_path.with_suffix("")

    def decompress() -> Path:
        with bz2.BZ2File(iso_path, "rb") as input_file:
            with open(decompressed_path, "wb") as output_file:
                for data in iter(lambda: input_file.read(100 * 1024), b""):
                    output_file.write(data)

        # remove the original compressed file after successful write - not needed
        iso_path.unlink(missing_ok=True)
        return decompressed_path

    return await loop.run_in_executor(None, decompress)
