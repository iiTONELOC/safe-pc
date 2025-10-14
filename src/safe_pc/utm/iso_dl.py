from pathlib import Path
from logging import getLogger
from tempfile import TemporaryDirectory
from collections.abc import Callable, Awaitable

from safe_pc.utm.utils import compute_sha256
from safe_pc.proxmox_auto_installer.utils import handle_download

LOGGER = getLogger(__name__)


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
        LOGGER.info(f"ISO does not exist at {iso_path}, need to download.")
        return True

    LOGGER.info(f"ISO already exists at {iso_path}, verifying SHA-256...")
    hash_file = iso_path.with_suffix(".sha256")
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
        self.on_update = on_update
        self.expected_sha256 = None
        self.get_iso_info = get_iso_info
        self.temp_dir = TemporaryDirectory()

    async def run(self, dl_if_exists: bool = False) -> bool:
        """Perform the full download + verify process manually."""
        try:

            url, self.expected_sha256 = await self.get_iso_info()
            if not url:
                raise ISODownloadError("Failed to resolve ISO download URL")

            self.iso_name = Path(url).name
            self.iso_path = Path(self.temp_dir.name) / self.iso_name

            if not dl_if_exists and not need_to_download(
                self.dest_dir / self.iso_name, self.expected_sha256
            ):
                LOGGER.info("ISO already exists and is valid, skipping download.")
                self.verified = True
                self._cleanup()
                return True

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
            return True

        except Exception as e:
            LOGGER.error(f"ISO download/verification failed: {e}")
            self.verified = False
            self._cleanup()
            return False

    def _finalize(self):
        if self.verified and self.iso_path and self.expected_sha256:
            dest_path = self.dest_dir / Path(self.iso_path).name
            LOGGER.info(f"Moving verified ISO to {dest_path}")
            self.dest_dir.mkdir(parents=True, exist_ok=True)
            Path(self.iso_path).replace(dest_path)
            (dest_path.with_suffix(".sha256")).write_text(self.expected_sha256)
        self.temp_dir.cleanup()

    def _cleanup(self):
        if self.iso_path and Path(self.iso_path).exists():
            Path(self.iso_path).unlink(missing_ok=True)
        self.temp_dir.cleanup()

    async def __aenter__(self):
        return await self.run()

    async def __aexit__(
        self, _: type[BaseException] | None, exc: BaseException | None, __: object
    ):
        if exc:
            LOGGER.warning("Cleaning up due to error...")
            self._cleanup()

    def __await__(self, dl_if_exists: bool = False):
        """Allow `await ISODownloader(...)` directly."""
        return self.run(dl_if_exists=dl_if_exists).__await__()
