import bz2
import asyncio
from typing import Any
from pathlib import Path
from logging import getLogger
from httpx import AsyncClient
from collections.abc import Callable
from socket import gethostname, gethostbyname


LOGGER = getLogger(__name__)


def get_local_ip() -> str:
    """Gets the local IP address of the machine.

    Returns:
        str: The local IP address.
    """
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
        return decompressed_path

    return await loop.run_in_executor(None, decompress)
