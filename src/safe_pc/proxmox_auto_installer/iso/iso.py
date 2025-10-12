import shutil
import aiofiles
from os import chmod
from uuid import uuid4
from typing import Any
from pathlib import Path
from logging import getLogger
from collections.abc import Callable
from safe_pc.utils import get_local_ip
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
from safe_pc.proxmox_auto_installer.answer_file.answer_file import create_answer_file_from_toml, ProxmoxAnswerFile, NETWORK_CONFIG_DEFAULTS

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

    async def download(self, on_update: Callable[[int,int,str], Any]= lambda x,t,y : print(f"{x/t}%, {y}")) -> bool:
        """Downloads the ISO file to the specified directory.

        Args:
            on_update (Callable | None): Optional callback for progress updates.

        Returns:
            bool: True if the ISO is successfully downloaded or already valid, False otherwise.
        """
        await on_update(0,14 ,"Fetching latest Proxmox ISO URL...") 
        if not validate_iso_url(self.url):
            raise ValueError(f"Invalid ISO URL: {self.url}")

        if not self.downloaded and not need_to_download(
            self.iso_path, self.sha256 or ""
        ):
            self.downloaded = True
            await on_update(4,14, "ISO already downloaded and verified.")
            return True

        self.iso_dir.mkdir(parents=True, exist_ok=True)
        await on_update(1,14, "Starting Download") 
        await handle_iso_download(self.url, self.iso_path, on_update)
        await on_update(3,14, "Download complete, verifying...") 
        if self.sha256 and not await verify_sha256(
            for_file_path=str(self.iso_path), expected_hash=self.sha256
        ):
            self.iso_path.unlink(missing_ok=True)
            self.LOGGER.warning(
                "SHA256 hash mismatch after download. Removed invalid ISO."
            )
        await on_update(4,14, "ISO verified successfully.")
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
        await create_auto_installer_mode_file(
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
        # 9. Discovery script
        # need to grab dns, gateway, ip, from the answer file
        _answer_obj:ProxmoxAnswerFile = create_answer_file_from_toml(answer_file)
        newtwork = _answer_obj.network
        
        dns = newtwork.dns or NETWORK_CONFIG_DEFAULTS["dns"]
        gw_ip = newtwork.gateway or NETWORK_CONFIG_DEFAULTS["gateway"]
        ip = newtwork.cidr or NETWORK_CONFIG_DEFAULTS["cidr"]       
        
        
        await on_update(9, "Adding discovery script to initrd...")
        discovery_script_path = Path(__file__).parent / "bash_scripts" / "discovery.t.sh"
        # read the script and replace the placeholders with actual values
        script_contents = ""
        async with aiofiles.open(discovery_script_path, mode="r") as f:
            script_contents = await f.read()
                
            script_contents = script_contents.replace("{{dns}}", dns)
            script_contents = script_contents.replace("{{gw_ip}}", gw_ip)
            script_contents = script_contents.replace("{{ip}}", ip)
            script_contents = script_contents.replace("{{config_server}}", get_local_ip())
            script_contents = script_contents.replace("{{job_id}}", self.job_id)
        
        discovery_script_path = Path(__file__).parent / "bash_scripts" / "discovery.sh"
        
        # write the modified script contents
        async with aiofiles.open(discovery_script_path, mode="w") as f:
            await f.write(script_contents)
        self.LOGGER.info(
            f"Copying discovery script from {discovery_script_path} to: {self.extracted_ram_disk}"
        )
        shutil.copy(
            src=discovery_script_path,
            dst=self.extracted_ram_disk / "discovery.sh",
        )
        self.LOGGER.info("Added discovery script to initrd, setting executable bit")
        (self.extracted_ram_disk / "discovery.sh").chmod(0o755)

        # 10. Modify init
   
        await on_update(10, "Modifying initrd init script...")

        self.LOGGER.info("Modifying init script to run discovery script")
        init_file_path = self.extracted_ram_disk / "init"
        async with aiofiles.open(init_file_path, mode="r") as f:
            init_contents = await f.readlines()

        for i, line in enumerate(init_contents):
            if line.strip().startswith("INSTALLER_SQFS="):
                init_contents.insert(
                    i + 1, '\necho "[*] Running discovery script..."\n'
                )
                init_contents.insert(i + 2, "chmod +x discovery.sh\n")
                init_contents.insert(i + 3, "/discovery.sh\n")
                init_contents.insert(i + 4, 'echo "[*] Discovery script finished."\n')
                break

        async with aiofiles.open(init_file_path, mode="w") as f:
            await f.writelines(init_contents)

        # ensure init is executable
        chmod(init_file_path, 0o755)

        self.LOGGER.info("Modified init script successfully, repacking initrd.img")
        # 11. Repack initrd.img
     
        await on_update(11, "Repacking initrd.img...")
    
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
        
        await on_update(12, "Replacing initrd.img in ISO...")
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

        await on_update(13, "Repacking modified ISO...") 

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

        await on_update(14, "Finished...")
        self.LOGGER.info(f"Repacked modified ISO to {out}")
        return out
    
    def move_iso_to_final_location(self, final_dir: Path | None = None) -> Path:
        """
        Move the ISO into the root isos dir (/.../data/isos). Overwrite if target exists.
        If self.modified_iso_path doesn't exist, auto-detect the newest ISO under repacked/
        (fallback to any *.iso under work_dir).
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
