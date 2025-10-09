from os import chmod
import shutil
import asyncio
import aiofiles
from uuid import uuid4
from sys import platform
from pathlib import Path
from typing import Callable
from logging import getLogger


from safe_pc.proxmox_auto_installer.iso.extractor import (
    repack_iso_oscdimg,
    unpack_iso_7z,
)
from safe_pc.proxmox_auto_installer.iso.helpers import (
    create_answer_file,
    create_auto_installer_mode_file,
)
from safe_pc.proxmox_auto_installer.utils import unpack_initrd, repack_initrd
from safe_pc.utils import setup_logging, verify_sha256, handle_keyboard_interrupt
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
        await on_update(1, "Fetching latest Proxmox ISO URL...") if on_update else None
        if not validate_iso_url(self.url):
            raise ValueError(f"Invalid ISO URL: {self.url}")

        if not self.downloaded and not need_to_download(
            self.iso_path, self.sha256 or ""
        ):
            self.downloaded = True
            await on_update(4, "ISO already downloaded and verified.")
            return True

        self.iso_dir.mkdir(parents=True, exist_ok=True)
        await on_update(2, "Starting Download") if on_update else None
        await handle_iso_download(self.url, self.iso_path, on_update)
        await on_update(3, "Download complete, verifying...") if on_update else None
        if self.sha256 and not await verify_sha256(
            for_file_path=self.iso_path, expected_hash=self.sha256
        ):
            self.iso_path.unlink(missing_ok=True)
            self.LOGGER.warning(
                "SHA256 hash mismatch after download. Removed invalid ISO."
            )
        await on_update(4, "ISO verified successfully.") if on_update else None
        return self.iso_path.exists()


class ModifiedProxmoxISO:
    """
    Represents a Proxmox ISO image with additional modification capabilities.
    """

    LOGGER = getLogger("safe_pc.proxmox_auto_installer.iso:ModifiedProxmoxISO")

    def __init__(
        self,
        base_iso: ProxmoxISO,
        job_id: str,
        modified_iso_path: Path | None = None,
    ) -> None:
        self.base_iso = base_iso
        self.job_id = job_id
        self.work_dir = base_iso.iso_dir / f"job-{job_id or uuid4().__str__()}"
        self.modified_iso_path = (
            modified_iso_path or self.work_dir / f"modified-{self.base_iso.iso_name}"
        )

        self.repacked_iso_dir = self.work_dir / "repacked"
        self.extracted_iso_dir = self.work_dir / "extracted"
        self.extracted_ram_disk = self.work_dir / "extracted_ram_disk" / "initrd.img"
        self.repacked_ram_disk = self.work_dir / "repacked_ram_disk" / "initrd.img"

        for path in [
            self.work_dir,
            self.repacked_iso_dir,
            self.extracted_iso_dir,
            self.extracted_ram_disk.parent,
            self.repacked_ram_disk.parent,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    async def create_modified_iso(
        self, answer_file: str, on_update: Callable | None = None
    ) -> Path | None:
        """Performs the actual ISO modification."""
        self.LOGGER.info(f"Modifying ISO at {self.base_iso.iso_path}")
        await on_update(5, "Extracting Proxmox ISO...") if on_update else None
        coroutine_status = None
        if platform == "win32":
            coroutine_status = await unpack_iso_7z(
                iso_path=self.base_iso.iso_path,
                dest_path=self.extracted_iso_dir,
            )
        else:
            self.LOGGER.warning(
                "ISO modification on Unix-like systems not implemented yet."
            )
            return None

        self.LOGGER.info(
            f"Unpacked ISO to {self.extracted_iso_dir}. Routine result: {coroutine_status}"
        )

        # 6. Create the auto-installer-mode.toml file
        if on_update:
            await on_update(6, "Creating auto-installer-mode.toml...")
        ok = create_auto_installer_mode_file(
            path_to_unpacked_iso=self.extracted_iso_dir,
            path_to_answer_file="/tmp/answer.toml",
            verify_flag=True,
        )

        self.LOGGER.info("Created auto-installer-mode.toml")

        # 7. Extract initrd.img

        if on_update:
            await on_update(7, "Extracting initrd.img...")

        ok = await unpack_initrd(
            initrd_path=self.extracted_iso_dir / "boot" / "initrd.img",
            dest_dir=self.extracted_ram_disk.parent,
        )
        if not ok:
            self.LOGGER.error("Failed to unpack initrd.img")
            return None

        self.LOGGER.info(f"Extracted initrd.img to {self.extracted_ram_disk.parent}")
        # 8. Add answer file
        if on_update:
            await on_update(8, "Adding answer file to initrd...")
        ok = create_answer_file(
            path_to_unpacked_iso=self.extracted_ram_disk.parent,
            using_answer_file=answer_file,
            verify_flag=False,
        )

        self.LOGGER.info("Added answer file to initrd")
        # 9. Discovery script
        if on_update:
            await on_update(9, "Adding discovery script to initrd...")
        discovery_script_path = Path(__file__).parent / "bash_scripts" / "discovery.sh"
        self.LOGGER.info(
            f"Copying discovery script from {discovery_script_path} to: {self.extracted_ram_disk.parent}"
        )
        shutil.copy(
            src=discovery_script_path,
            dst=self.extracted_ram_disk.parent / "discovery.sh",
        )
        self.LOGGER.info("Added discovery script to initrd, setting executable bit")
        (self.extracted_ram_disk.parent / "discovery.sh").chmod(0o755)

        # 10. Modify init
        if on_update:
            await on_update(10, "Modifying initrd init script...")

        self.LOGGER.info("Modifying init script to run discovery script")
        init_file_path = self.extracted_ram_disk.parent / "init"
        async with aiofiles.open(init_file_path, mode="r") as f:
            init_contents = await f.readlines()

        for i, line in enumerate(init_contents):
            if line.strip().startswith("INSTALLER_SQFS="):
                init_contents.insert(
                    i + 1, '\necho "[*] Running discovery script..."\n'
                )
                init_contents.insert(i + 2, "chmod +x /discovery.sh\n")
                init_contents.insert(i + 3, "/discovery.sh\n")
                init_contents.insert(i + 4, 'echo "[*] Discovery script finished."\n')
                break

        async with aiofiles.open(init_file_path, mode="w") as f:
            await f.writelines(init_contents)

        self.LOGGER.info("Modified init script successfully, repacking initrd.img")
        # 11. Repack initrd.img
        if on_update:
            await on_update(11, "Repacking initrd.img...")
        if platform == "win32":
            ok = await repack_initrd(
                src_dir=self.extracted_ram_disk.parent,
                out_path=self.repacked_ram_disk,
                zstd_level=19,
            )
            if not ok:
                self.LOGGER.error("Failed to repack initrd.img")
                return None
        else:
            self.LOGGER.warning("Repacking not implemented for Unix-like systems.")
            return None

        self.LOGGER.info(
            f"Repacked initrd.img to {self.repacked_ram_disk}, replacing in ISO"
        )
        # 12. Replace initrd.img in boot
        if on_update:
            await on_update(12, "Replacing initrd.img in ISO...")
            boot_initrd_path = self.extracted_iso_dir / "boot" / "initrd.img"

        # Remove existing file if present (handle permission issues on Windows)
        if boot_initrd_path.exists():
            try:
                boot_initrd_path.unlink()
            except PermissionError:
                chmod(boot_initrd_path, 0o666)
                boot_initrd_path.unlink()
        self.LOGGER.info(f"Moving new initrd.img into place at {boot_initrd_path}")
        # Move new initrd.img into place asynchronously
        await asyncio.to_thread(
            shutil.move,
            str(self.repacked_ram_disk),
            str(boot_initrd_path),
        )
        out = self.repacked_iso_dir / f"auto-installer-{self.job_id}.iso"
        self.LOGGER.info(
            f"Replaced initrd.img in ISO successfully, repacking ISO to {out}"
        )
        # 13. Repack entire ISO

        await on_update(13, "Repacking modified ISO...") if on_update else None

        self.LOGGER.info("Repacking modified ISO with oscdimg...")
        ok = await repack_iso_oscdimg(
            source_dir=self.extracted_iso_dir,
            output_iso=out,
        )
        if not ok:
            self.LOGGER.error("Failed to repack modified ISO")
            return None

        await on_update(13.5, "Finished...") if on_update else None
        self.LOGGER.info(f"Repacked modified ISO to {out}")
        return out


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
