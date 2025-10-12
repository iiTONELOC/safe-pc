from pathlib import Path
from httpx import AsyncClient
from logging import getLogger
from collections.abc import Callable
from contextlib import asynccontextmanager

from aiofiles import open as aio_open
from tqdm.asyncio import tqdm_asyncio

HTTP_CHUNK_SIZE = 1024 * 1024  # 1 MB
BUFFER_SIZE = HTTP_CHUNK_SIZE * 4  # 4 MB
LOGGER = getLogger(__name__)


@asynccontextmanager
async def _download_context(url: str, dest_path: Path):
    client = AsyncClient(timeout=None)
    try:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            async with aio_open(dest_path, "wb") as file:
                yield resp, file
    finally:
        await client.aclose()


def _should_use_progress(*, use_progress: bool = False, progress: object = None) -> bool:
    return bool(use_progress) and progress is not None


from typing import Any

def _init_progress(*, use_progress: bool = False, size: int = 0) -> Any:
    if not use_progress:
        return None
    return tqdm_asyncio(total=size, unit="B", unit_scale=True, desc="Downloading")




async def _update_progress(
    n: int,
    *,
    use_progress: bool = False,
    progress: Any | None = None,
    downloaded: int = 0,
    size: int = 0,
    on_update: Callable[[int,int, str], Any]|None = None,
) -> int:
    downloaded += n
    if _should_use_progress(use_progress=use_progress, progress=progress):
        if progress is not None:
            progress.update(n)
    elif on_update:
        await on_update(downloaded,size, "Downloading Proxmox VE ISO...")
    return downloaded


async def _single_downloader_async(
    url: str, dest_path: Path, size: int, on_update:Callable[[int,int, str], Any]|None = None,
):
    downloaded = 0
    use_progress = on_update is None
    progress = _init_progress(use_progress=use_progress, size=size)
    buffer = bytearray()

    try:
        async with _download_context(url, dest_path) as (resp, file):
            async for chunk in resp.aiter_bytes(chunk_size=HTTP_CHUNK_SIZE):
                if not chunk:
                    continue
                buffer.extend(chunk)
                if len(buffer) >= BUFFER_SIZE:
                    await file.write(buffer)
                    downloaded = await _update_progress(
                        len(buffer),
                        use_progress=use_progress,
                        progress=progress,
                        downloaded=downloaded,
                        size=size,
                        on_update=on_update,
                    )
                    buffer.clear()

            if buffer:
                await file.write(buffer)
                downloaded = await _update_progress(
                    len(buffer),
                    use_progress=use_progress,
                    progress=progress,
                    downloaded=downloaded,
                    size=size,
                    on_update=on_update,
                )
    except Exception:
        if dest_path.exists():
            dest_path.unlink()
        raise
    finally:
        if progress:
            progress.close()


async def handle_download(url: str, dest_path: Path, on_update: Callable[[int,int, str], Any]|None = None,):
    """
    Asynchronously downloads a file from the specified URL to the given destination path.
    This function retrieves the file size via a HEAD request for progress tracking, ensures the destination directory exists,
    and downloads the file while optionally calling an on_update hook. If the download fails, it cleans up any partial file.
    Args:
        url (str): The URL of the file to download.
        dest_path (Path): The local filesystem path where the downloaded file will be saved.
        on_update (Callable | None, optional): An optional callback function for progress updates. Defaults to None.
    Raises:
        Exception: Propagates any exception encountered during the download process after logging and cleanup.

    Note:
        Default behavior uses a progress bar for console applications. If on_update is provided, it will be used instead.
    """

    try:
        # get the size of the file (used for progress bar)
        async with AsyncClient(timeout=30) as client:
            head = await client.head(url, follow_redirects=True)
            head.raise_for_status()
            size = int(head.headers.get("Content-Length", "0"))

        # dest_path.parent.mkdir(parents=True, exist_ok=True)
        LOGGER.info(f"Starting download: {url} to {dest_path} ({size} bytes)")
        await _single_downloader_async(url, dest_path, size, on_update)
        LOGGER.info(msg=f"Download complete: {dest_path}")
    except Exception as e:
        LOGGER.error(f"Download failed: {e}")
        if dest_path.exists():
            dest_path.unlink()
        raise
