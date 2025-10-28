import errno
import traceback
from typing import Any
from pathlib import Path
from httpx import AsyncClient
from logging import getLogger
from tempfile import TemporaryDirectory
from contextlib import asynccontextmanager
from collections.abc import Callable, Awaitable

from utm.utils import compute_sha256

from aiofiles import open as aio_open
from tqdm.asyncio import tqdm_asyncio

LOGGER = getLogger(__name__)


HTTP_CHUNK_SIZE = 1024 * 1024  # 1 MB
BUFFER_SIZE = HTTP_CHUNK_SIZE * 4  # 4 MB


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
    on_update: Callable[[int, int, str], Any] | None = None,
) -> int:
    downloaded += n
    if _should_use_progress(use_progress=use_progress, progress=progress):
        if progress is not None:
            progress.update(n)
    elif on_update:
        await on_update(downloaded, size, "Downloading Proxmox VE ISO...")
    return downloaded


async def _single_downloader_async(
    url: str,
    dest_path: Path,
    size: int,
    on_update: Callable[[int, int, str], Any] | None = None,
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


async def handle_download(
    url: str,
    dest_path: Path,
    on_update: Callable[[int, int, str], Any] | None = None,
):
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


def need_to_download(iso_path: Path, expected_sha256: str) -> bool:
    """Determines if the ISO needs to be downloaded based on its existence and
    SHA-256 checksum.

    Args:
        iso_path (Path): The path to the ISO file.
        expected_sha256 (str): The expected SHA-256 checksum.

    Returns:
        bool: True if the ISO needs to be downloaded, False otherwise.
    """
    if not iso_path.exists():
        # if the file ends in a .bz2, check for the decompressed version too
        if iso_path.suffix == ".bz2" and (
            iso_path.with_suffix("").exists() or iso_path.with_suffix("").with_suffix(".iso").exists()
        ):
            LOGGER.info(f"Decompressed ISO already exists at {iso_path.with_suffix('')}, no need to download.")
            return False
        LOGGER.info(f"ISO does not exist at {iso_path}, need to download.")
        return True

    LOGGER.info(f"ISO already exists at {iso_path}, verifying SHA-256...")
    hash_file = iso_path.with_name(iso_path.name.replace(".iso", "") + ".sha256")
    LOGGER.info(f"Looking for existing hash file at {hash_file}...")

    existing_hash = hash_file.read_text().strip() if hash_file.exists() else ""

    if existing_hash.lower() == expected_sha256.lower():
        LOGGER.info("Existing ISO is valid, no need to re-download.")
        return False
    else:
        LOGGER.warning("Existing ISO is invalid, need to re-download.")
        return True


class ISODownloadError(Exception):
    """Raised when ISO download or verification fails."""


class ISODownloader:
    """Context-managed or direct ISO downloader and verifier."""

    def __init__(
        self,
        get_iso_info: Callable[[], Awaitable[tuple[str, str]]],
        dest_dir: Path,
        on_update: Callable[[int, int, str], None] | None = None,
    ):
        self.iso_name = None
        self.iso_path = None
        self.verified = False
        self.dest_dir = dest_dir
        self.dest_path = None
        self.on_update = on_update
        self.expected_sha256 = None
        self.get_iso_info = get_iso_info
        self.temp_dir = TemporaryDirectory()

    async def run(self, dl_if_exists: bool = False) -> "ISODownloader":
        """Perform the full download + verify process manually."""
        try:

            url, self.expected_sha256 = await self.get_iso_info()
            if not url:
                raise ISODownloadError("Failed to resolve ISO download URL")

            self.iso_name = Path(url).name
            self.iso_path = Path(self.temp_dir.name) / self.iso_name

            LOGGER.info(f"Checking if ISO needs to be downloaded at {self.dest_dir / self.iso_name}...")

            if not dl_if_exists and not need_to_download(self.dest_dir / self.iso_name, self.expected_sha256):
                LOGGER.info("ISO already exists and is valid, skipping download.")
                self.verified = True
                self._cleanup()
                return self

            LOGGER.info(f"Downloading ISO to temp: {self.iso_path}")

            # ensure the destination directory exists
            self.dest_dir.mkdir(parents=True, exist_ok=True)

            await handle_download(url, self.iso_path, self.on_update)
            actual_hash = await compute_sha256(str(self.iso_path))

            if actual_hash.lower() != self.expected_sha256.lower():
                LOGGER.error("SHA256 mismatch, possible tampering")
                raise ISODownloadError("Checksum verification failed")

            LOGGER.info("Checksum verified successfully.")
            self.verified = True
            self._finalize()
            return self

        except Exception as e:
            LOGGER.error(f"ISO download/verification failed: {e}")
            traceback.print_exc()
            self.verified = False
            self._cleanup()
            return self

    def _finalize(self):
        if self.verified and self.iso_path and self.expected_sha256:
            self.dest_path = self.dest_dir / Path(self.iso_path).name
            LOGGER.info(f"Moving verified ISO to {self.dest_path}")
            self.dest_dir.mkdir(parents=True, exist_ok=True)

            try:
                Path(self.iso_path).replace(self.dest_path)
            except OSError as e:
                if e.errno == errno.EXDEV:
                    # Handle cross-device move
                    import shutil

                    shutil.copy2(self.iso_path, self.dest_path)
                    Path(self.iso_path).unlink()
                else:
                    LOGGER.error(f"Failed to move ISO to destination: {e}")
                    raise

            (self.dest_path.with_suffix(".sha256")).write_text(self.expected_sha256)

        self.temp_dir.cleanup()

    def _cleanup(self):
        if self.iso_path and Path(self.iso_path).exists():
            Path(self.iso_path).unlink(missing_ok=True)
        self.temp_dir.cleanup()

    async def __aenter__(self):
        return await self.run()

    async def __aexit__(self, _: type[BaseException] | None, exc: BaseException | None, __: object):
        if exc:
            LOGGER.warning("Cleaning up due to error...")
            self._cleanup()

    def __await__(self, dl_if_exists: bool = False):
        """Allow `await ISODownloader(...)` directly."""
        return self.run(dl_if_exists=dl_if_exists).__await__()
