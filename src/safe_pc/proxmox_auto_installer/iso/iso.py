from pathlib import Path
from typing import Callable
from logging import getLogger
from datetime import datetime

from safe_pc.proxmox_auto_installer.answer_file.answer_file import ProxmoxAnswerFile
from safe_pc.utils.logs import setup_logging
from safe_pc.utils.crypto.crypto import verify_sha256
from safe_pc.utils.utils import handle_keyboard_interrupt
from safe_pc.proxmox_auto_installer.iso.downloader import (
    validate_iso_url,
    need_to_download,
    handle_iso_download,
    get_iso_folder_path,
    get_latest_proxmox_iso_url,
)


class ProxmoxISO:
    """
    Represents a Proxmox ISO image with metadata and download utilities.
    """

    LOGGER = getLogger("safe_pc.proxmox_auto_installer.iso:ProxmoxISO")

    def __init__(self, url: str, sha256: str | None = None) -> None:
        self.url = url
        self.sha256 = sha256
        self.downloaded = False
        self.iso_name = self._extract_iso_name()
        self.iso_dir = get_iso_folder_path(Path(self.iso_name).stem)
        self.iso_path = self.iso_dir / self.iso_name

    @classmethod
    async def new(cls, url: str | None = None, sha256: str | None = None):
        """
        Asynchronous constructor that fetches the latest ISO URL and SHA256 if not provided.
        """
        if not url:
            url, sha256 = await get_latest_proxmox_iso_url()
        return cls(url, sha256)

    def _extract_iso_name(self) -> str:
        """Extracts the ISO filename from the URL."""
        return self.url.split("/")[-1]

    async def download(self, on_update: Callable | None = None) -> bool:
        """Downloads the ISO file to the specified directory.

        Args:
            on_update (Callable | None): Optional callback for progress updates.

        Returns:
            bool: True if the ISO is successfully downloaded or already valid, False otherwise.
        """
        if not validate_iso_url(self.url):
            raise ValueError(f"Invalid ISO URL: {self.url}")

        if not self.downloaded and not need_to_download(
            self.iso_path, self.sha256 or ""
        ):
            self.downloaded = True
            return True

        self.iso_dir.mkdir(parents=True, exist_ok=True)
        await handle_iso_download(self.url, self.iso_path, on_update)
        if self.sha256 and not await verify_sha256(
            for_file_path=self.iso_path, expected_hash=self.sha256
        ):
            self.iso_path.unlink(missing_ok=True)
            self.LOGGER.warning(
                "SHA256 hash mismatch after download. Removed invalid ISO."
            )

        return self.iso_path.exists()


class ModifiedProxmoxISO:
    """
    Represents a Proxmox ISO image with additional modification capabilities.

    Args:
        base_iso (ProxmoxISO): The base Proxmox ISO to modify.
        modified_iso_path (Path | None): Optional path for the modified ISO.
        If not provided, a default path within the base_iso dir is generated.
    """

    LOGGER = getLogger("safe_pc.proxmox_auto_installer.iso:ModifiedProxmoxISO")

    def __init__(
        self, base_iso: ProxmoxISO, modified_iso_path: Path | None = None
    ) -> None:
        self.base_iso = base_iso
        self.modified_iso_path = modified_iso_path or base_iso.iso_path.with_name(
            f"{base_iso.iso_path.stem}-modified-{datetime.now().strftime("%Y%m%d%H%M%S")}{base_iso.iso_path.suffix}"
        )

    async def create_modified_iso(
        self, answer_file: ProxmoxAnswerFile | None = None
    ) -> None:
        """Placeholder for ISO modification logic."""
        # TODO: Implement ISO modification logic here
        print("Modifying ISO... (not yet implemented)")


async def run():
    """
    Main asynchronous entry point for downloading the Proxmox ISO.
    """
    setup_logging()
    iso = await ProxmoxISO.new()
    await iso.download()


@handle_keyboard_interrupt
def main():
    """Main entry point for the Proxmox ISO downloader module."""
    import asyncio

    asyncio.run(run())


if __name__ == "__main__":  # pragma: no cover
    main()
