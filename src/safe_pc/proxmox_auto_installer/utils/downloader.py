from pathlib import Path
from logging import getLogger
from httpx import AsyncClient
from safe_pc.utils.utils import handle_keyboard_interrupt_async

from aiofiles import open as aio_open
from tqdm.asyncio import tqdm_asyncio


HTTP_CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
LOGGER = getLogger("capstone.utils.downloader" if __name__ == "__main__" else __name__)


@handle_keyboard_interrupt_async
async def _single_downloader_async(url: str, dest_path: Path, size: int):
    """
    Downloads a file from the specified URL to the given destination path using a single async connection.
    Args:
        url (str): The URL of the file to download.
        dest_path (Path): The local file path where the downloaded file will be saved.
        size (int): The expected size of the file in bytes, used for progress tracking.
    """
    LOGGER.info("Falling back to single async connection download")
    async with AsyncClient(timeout=30) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            buffer = bytearray()
            async with aio_open(dest_path, "wb") as f:
                progress = tqdm_asyncio(
                    total=size, unit="B", unit_scale=True, desc="Downloading"
                )
                try:
                    async for chunk in resp.aiter_bytes(chunk_size=HTTP_CHUNK_SIZE):
                        if chunk:
                            buffer.extend(chunk)
                            if len(buffer) >= HTTP_CHUNK_SIZE * 4:
                                await f.write(buffer)
                                progress.update(len(buffer))
                                buffer.clear()
                    if buffer:
                        await f.write(buffer)
                        progress.update(len(buffer))
                except Exception as _:
                    if dest_path.exists():
                        dest_path.unlink()
                    LOGGER.error(f"Download failed during streaming: {url}\nError: {_}")
                finally:
                    progress.close()


@handle_keyboard_interrupt_async
async def handle_download(url: str, dest_path: Path):
    """
    Asynchronously downloads a file from the specified URL to the given destination path.

    Args:
        url (str): The URL of the file to download.
        dest_path (Path): The destination path where the file will be saved.
    Raises:
        Exception: If the download fails for any reason other than KeyboardInterrupt.
    """
    try:
        async with AsyncClient(timeout=30) as client:
            _head = await client.head(url, follow_redirects=True)
            _head.raise_for_status()
            size_str: str = _head.headers.get("Content-Length", "0")
            size: int = int(size_str)

            await _single_downloader_async(url, dest_path, size)
        LOGGER.info(f"Download complete: {dest_path}")
    except Exception as e:
        LOGGER.error(f"Download failed: {e}")
        if dest_path.exists():
            dest_path.unlink()
        LOGGER.error(f"Download failed: {e}")
