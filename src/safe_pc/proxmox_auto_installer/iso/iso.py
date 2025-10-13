from uuid import uuid4
from typing import Any
from pathlib import Path
from logging import getLogger
from collections.abc import Callable
from safe_pc.proxmox_auto_installer.iso.helpers import (
    create_answer_file,
    create_auto_installer_mode_file,
)
from safe_pc.proxmox_auto_installer.iso.tools import (
    unpack_initrd,
    repack_initrd,
    xorriso_extract_iso,
    xorriso_repack_iso,
    replace_initrd_file
)
from safe_pc.utils import setup_logging, verify_sha256, handle_keyboard_interrupt
from safe_pc.proxmox_auto_installer.iso.downloader import (
    validate_iso_url,
    need_to_download,
    handle_iso_download,
    get_iso_folder_path,
    get_latest_proxmox_iso_url,
)

TOTAL_STEPS = 12
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

    async def download(self, on_update: Callable[[int,int,str], Any]= lambda x,t,y : print(f"{x/t}%, {y}")) -> bool:
        """Downloads the ISO file to the specified directory.

        Args:
            on_update (Callable | None): Optional callback for progress updates.

        Returns:
            bool: True if the ISO is successfully downloaded or already valid, False otherwise.
        """
        await on_update(0, TOTAL_STEPS ,"Fetching latest Proxmox ISO URL...") 
        if not validate_iso_url(self.url):
            raise ValueError(f"Invalid ISO URL: {self.url}")

        if not self.downloaded and not need_to_download(
            self.iso_path, self.sha256 or ""
        ):
            self.downloaded = True
            await on_update(4, TOTAL_STEPS, "ISO already downloaded and verified.")
            return True

        self.iso_dir.mkdir(parents=True, exist_ok=True)
        await on_update(0, TOTAL_STEPS, "Starting Download") 
        await handle_iso_download(self.url, self.iso_path, on_update)
        await on_update(TOTAL_STEPS, TOTAL_STEPS, "Download complete, verifying...") 
        if self.sha256 and not await verify_sha256(
            for_file_path=str(self.iso_path), expected_hash=self.sha256
        ):
            self.iso_path.unlink(missing_ok=True)
            self.LOGGER.warning(
                "SHA256 hash mismatch after download. Removed invalid ISO."
            )
        await on_update(TOTAL_STEPS, TOTAL_STEPS, "ISO verified successfully.")
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
        self.extracted_ram_disk = self.work_dir / "extracted_ram_disk"
        self.repacked_ram_disk = self.work_dir / "repacked_ram_disk" / "initrd.img"

        for path in [
            self.work_dir,
            self.repacked_iso_dir,
            self.extracted_iso_dir,
            self.extracted_ram_disk,
            self.repacked_ram_disk.parent,
        ]:
            path.mkdir(parents=True, exist_ok=True)

    async def create_modified_iso(
        self, answer_file: str, on_update: Callable[[int,str], Any]
    ) -> Path | None:
        """Performs the actual ISO modification."""
        self.LOGGER.info(f"Modifying ISO at {self.base_iso.iso_path}")

        # 5. Extract ISO
        await on_update(5, "Extracting Proxmox ISO...") 
        coroutine_status = await xorriso_extract_iso(
            iso_path=self.base_iso.iso_path,
            out_dir=self.extracted_iso_dir,
        )
        self.LOGGER.info(
            f"Unpacked ISO to {self.extracted_iso_dir}. Routine result: {coroutine_status}"
        )

        # 6. Create the auto-installer-mode.toml file
        await on_update(6, "Creating auto-installer-mode.toml...")
        create_auto_installer_mode_file(
            path_to_unpacked_iso=self.extracted_iso_dir,
            job_id=self.job_id,
            verify_flag=True,
        )

        self.LOGGER.info("Created auto-installer-mode.toml")

        # 7. Extract initrd.img
        await on_update(7, "Extracting initrd.img...")

        ok = await unpack_initrd(
            initrd_path=self.extracted_iso_dir / "boot" / "initrd.img",
            out_dir=self.extracted_ram_disk,
        )

        if not ok:
            self.LOGGER.error("Failed to unpack initrd.img")
            return None

        self.LOGGER.info(f"Extracted initrd.img to {self.extracted_ram_disk}")

        # 8. Add answer file      
        await on_update(8, "Adding answer file to initrd...")
        create_answer_file(
            path_to_unpacked_iso=self.extracted_ram_disk,
            using_answer_file=answer_file,
            verify_flag=False,
        )

        self.LOGGER.info("Added answer file to initrd")
      
     
        await on_update(9, "Repacking initrd.img...")
    
        ok = await repack_initrd(
            unpacked_initrd_dir=self.extracted_ram_disk,
            output_initrd=self.repacked_ram_disk,
        )

        if not ok:
            self.LOGGER.error("Failed to repack initrd.img")
            return None
    
        self.LOGGER.info(
            f"Repacked initrd.img to {self.repacked_ram_disk}, replacing in ISO"
        )
        # 12. Replace initrd.img in boot
        
        await on_update(10, "Replacing initrd.img in ISO...")
        boot_initrd_path = self.extracted_iso_dir / "boot" / "initrd.img"

       
        await replace_initrd_file(
            new_file=self.repacked_ram_disk,
            dest_file=boot_initrd_path,
        )
        out = self.repacked_iso_dir / f"auto-installer-{self.job_id}.iso"
        self.LOGGER.info(
            f"Replaced initrd.img in ISO successfully, repacking ISO to {out}"
        )
        # 13. Repack entire ISO

        await on_update(11, "Repacking modified ISO...") 

        self.LOGGER.info(
            f"Repacking modified ISO with xorriso...: source {self.extracted_iso_dir} output {out}"
        )
        ok = await xorriso_repack_iso(
            unpacked_iso_dir=self.extracted_iso_dir,
            output_iso=out,
        )

        if not ok:
            self.LOGGER.error("Failed to repack modified ISO")
            return None

        await on_update(TOTAL_STEPS, "Finished...")
        self.LOGGER.info(f"Repacked modified ISO to {out}")
        return out
    
    def move_iso_to_final_location(self, final_dir: Path | None = None) -> Path:
        """
        Move the ISO into the root isos dir (/.../data/isos). Overwrite if target exists.
        """
        import os
        from pathlib import Path

        # 1) Resolve source
        src = Path(getattr(self, "modified_iso_path", "")) if getattr(self, "modified_iso_path", None) else None
        if not src or not src.exists():
            # Try the expected repacked/ location first
            repacked_dir = Path(self.work_dir) / "repacked"
            candidates = []
            if repacked_dir.exists():
                candidates.extend(repacked_dir.glob("*.iso")) # type: ignore
            # Fallback: any ISO under work_dir
            if not candidates:
                candidates = list(Path(self.work_dir).rglob("*.iso"))

            if not candidates:
                raise FileNotFoundError(
                    f"ISO to move not found. Tried modified_iso_path={self.modified_iso_path!s}, "
                    f"repacked_dir={repacked_dir}"
                )

            # Pick the newest by mtime
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            src = candidates[0]
            # Update pointer so future calls are consistent
            self.modified_iso_path = src
            self.LOGGER.info(f"[move_iso_to_final_location] Auto-selected ISO source: {src}")

        # 2) Resolve destination root (/.../data/isos)
        target_dir = final_dir or self.base_iso.iso_dir.parent
        target_dir.mkdir(parents=True, exist_ok=True)

        # Keep exact filename, overwrite atomically
        dst = target_dir / src.name
        os.replace(str(src), str(dst))

        # 3) Log & update
        self.LOGGER.info({
            "base_iso_path": str(self.base_iso.iso_path),
            "work_dir": str(self.work_dir),
            "moved_from": str(src),
            "final_iso_dir": str(target_dir),
            "final_iso_path": str(dst),
        })
        self.modified_iso_path = dst
        return dst



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
