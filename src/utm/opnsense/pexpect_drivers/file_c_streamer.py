from textwrap import wrap
from base64 import b64encode
from asyncio import sleep
from pexpect import spawn as pe_spawn, TIMEOUT, EOF  # type: ignore


def normalize_endings(data: str) -> str:
    """Normalize line endings to Unix style."""
    return data.replace("\r\n", "\n").replace("\r", "\n")


def base64_encode(data: str) -> str:
    """Encode data to base64 string."""
    return b64encode(data.encode("utf-8")).decode("utf-8")


async def stream_in_chunks(data: str, to_child: pe_spawn, chunk_size: int = 255) -> None:  # type: ignore
    """Stream data to pexpect child in chunks."""

    # Encode to base64 to avoid special character issues, ensuring unix line endings
    data = base64_encode(normalize_endings(data))
    for chunk in wrap(data, chunk_size):
        to_child.sendline(chunk)  # type: ignore
        await sleep(0.1)  # type: ignore

    # cleanup
    # signal end of input
    to_child.sendcontrol("d")
    await sleep(0.5)
    to_child.sendline("sync")
    await sleep(0.5)


async def stream_file_in_chunks(data: str, temp_file_path: str, dest_path: str, to_child: pe_spawn, chunk_size: int = 255) -> None:  # type: ignore
    """Stream file data to pexpect child in chunks."""

    # clean up any existing files
    to_child.sendline(f"rm -f {temp_file_path} {dest_path}")
    await sleep(0.5)

    # send the cat command to create the temp file
    to_child.sendline(f"cat > {temp_file_path}")
    await sleep(0.5)

    # stream the data in chunks
    await stream_in_chunks(data, to_child, chunk_size)

    # decode from base64 to destination file and remove temp
    to_child.sendline(f"base64 -d {temp_file_path} > {dest_path} && rm -f {temp_file_path}")
    await sleep(3)
