from uuid import uuid4
from typing import Any
from pathlib import Path
from logging import getLogger
from collections.abc import Callable

from proxmox_auto_installer.iso.helpers import (
    create_answer_file,
    create_auto_installer_mode_file,
)
from proxmox_auto_installer.iso.tools import (
    unpack_initrd,
    repack_initrd,
    xorriso_repack_iso,
    xorriso_extract_iso,
    replace_initrd_file,
)

from proxmox_auto_installer.iso.downloader import (
    validate_iso_url,
    get_iso_folder_path,
    get_latest_prox_url_w_hash,
)
from utm.utils import (
    setup_logging,
    ISODownloader,
    run_command_async,
    handle_keyboard_interrupt,
)


TOTAL_STEPS = 17
SAFE_PC_INSTALL_LOCATION = "/opt/safe_pc"


class ProxmoxISO:
    """
    Represents a Proxmox ISO image with metadata and download utilities.
    """

    LOGGER = getLogger("proxmox_auto_installer.iso:ProxmoxISO")

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
            url, sha256 = await get_latest_prox_url_w_hash()
        return cls(url, sha256)

    def _extract_iso_name(self) -> str:
        """Extracts the ISO filename from the URL."""
        return self.url.split("/")[-1]

    async def download(self, on_update: Callable[[int, int, str], Any] | None = None) -> bool:
        """Downloads the ISO file to the specified directory.

        Args:
            on_update (Callable | None): Optional callback for progress updates.

        Returns:
            bool: True if the ISO is successfully downloaded or already valid, False otherwise.
        """

        if not validate_iso_url(self.url):
            raise ValueError(f"Invalid ISO URL: {self.url}")

        if on_update:
            await on_update(0, TOTAL_STEPS, "Starting Download")
        downloaded = await ISODownloader(get_latest_prox_url_w_hash, dest_dir=self.iso_dir, on_update=on_update)
        return downloaded.verified


class ModifiedProxmoxISO:
    """
    Represents a Proxmox ISO image with additional modification capabilities.
    """

    LOGGER = getLogger("proxmox_auto_installer.iso:ModifiedProxmoxISO")

    def __init__(
        self,
        base_iso: ProxmoxISO,
        job_id: str,
        modified_iso_path: Path | None = None,
    ) -> None:
        self.base_iso = base_iso
        self.job_id = job_id
        self.work_dir = base_iso.iso_dir / f"job-{job_id or uuid4().__str__()}"
        self.modified_iso_path = modified_iso_path or self.work_dir / f"modified-{self.base_iso.iso_name}"

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

    async def create_modified_iso(self, answer_file: str, on_update: Callable[[int, str], Any]) -> Path | None:
        """Performs the actual ISO modification."""
        self.LOGGER.info(f"Modifying ISO at {self.base_iso.iso_path}")

        # 5. Extract ISO
        await on_update(5, "Extracting Proxmox ISO...")
        coroutine_status = await xorriso_extract_iso(
            iso_path=self.base_iso.iso_path,
            out_dir=self.extracted_iso_dir,
        )
        self.LOGGER.info(f"Unpacked ISO to {self.extracted_iso_dir}. Routine result: {coroutine_status}")

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

        self.LOGGER.info(f"Repacked initrd.img to {self.repacked_ram_disk}, replacing in ISO")
        # 12. Replace initrd.img in boot

        await on_update(10, "Replacing initrd.img in ISO...")
        boot_initrd_path = self.extracted_iso_dir / "boot" / "initrd.img"

        await replace_initrd_file(
            new_file=self.repacked_ram_disk,
            dest_file=boot_initrd_path,
        )
        out = self.repacked_iso_dir / f"auto-installer-{self.job_id}.iso"
        # self.LOGGER.info(f"Replaced initrd.img in ISO successfully, repacking ISO to {out}")

        # unsquash the rootfs
        # make an extracted squashfs dir
        extracted_squashfs_dir = self.work_dir / "extracted_squashfs"
        extracted_squashfs_dir.mkdir(parents=True, exist_ok=True)
        # 11. Unsquash the rootfs
        await on_update(11, "Unsquashing rootfs...")
        status = await run_command_async(
            "unsquashfs",
            "-no-xattrs",
            "-no-progress",
            "-ignore-errors",
            "-q",
            "-d",
            str(extracted_squashfs_dir),
            str(self.extracted_iso_dir / "pve-base.squashfs"),
            check=False,
        )
        if status.returncode not in [0, 2]:
            self.LOGGER.error(f"Failed to unsquash rootfs: {status.stderr}")  # type: ignore
            return None
        self.LOGGER.info(f"Unsquashed rootfs to {extracted_squashfs_dir}")

        # ensure the UTM is built
        await run_command_async("poetry", "run", "build-utm", check=True, cwd=Path(__file__).resolve().parents[3])
        await on_update(12, "Copying UTM to rootfs...")

        # copy the dist/safe_pc folder into the extracted squashfs
        dist_safe_pc_path = Path(__file__).resolve().parents[3] / "dist" / "safe_pc"
        target_safe_pc_path = extracted_squashfs_dir / "opt" / "safe_pc"

        if target_safe_pc_path.exists():
            await run_command_async("rm", "-rf", str(target_safe_pc_path), check=True)

        # ensure the opt folder exists, if not, create it
        (extracted_squashfs_dir / "opt").mkdir(parents=True, exist_ok=True)

        await run_command_async(
            "cp",
            "-r",
            str(dist_safe_pc_path),
            str(target_safe_pc_path.parent),
            check=True,
        )
        await on_update(13, "Setting executable permissions...")
        # ensure everything is executable
        await run_command_async(
            "chmod",
            "-R",
            "+x",
            str(target_safe_pc_path),
            check=True,
        )

        # create a service that will run safe_pc on boot
        # oneshot coupled with remainafterexit ensures the service only runs once, multiple calls to start
        # will not re-run the service once it has been marked as active
        # https://www.redhat.com/en/blog/systemd-oneshot-service
        await on_update(14, "Creating systemd service for first boot...")
        service_str = f"""
[Unit]
Description=Safe PC Post Startup Service
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart={SAFE_PC_INSTALL_LOCATION}/src/utm/scripts/post_startup.py

[Install]
WantedBy=multi-user.target
        """
        service_path = extracted_squashfs_dir / "etc" / "systemd" / "system" / "safe_pc_post_startup.service"
        service_path.write_text(service_str)
        self.LOGGER.info(f"Created systemd service at {service_path}")

        # enable the service by linking it to multi-user.target.wants
        wants_dir = extracted_squashfs_dir / "etc" / "systemd" / "system" / "multi-user.target.wants"
        wants_dir.mkdir(parents=True, exist_ok=True)
        link_path = wants_dir / "safe_pc_post_startup.service"
        await run_command_async(
            "ln",
            "-sf",
            str(service_path),
            str(link_path),
            check=True,
        )

        await on_update(15, "Repacking rootfs...")
        tmp_squash = Path("/tmp/pve-base.squashfs")

        status = await run_command_async(
            "mksquashfs",
            str(extracted_squashfs_dir),
            str(tmp_squash),
            "-noappend",
            "-comp",
            "xz",
            "-Xbcj",
            "x86",
            check=False,
        )
        if status.returncode != 0:
            self.LOGGER.error(f"Failed to repack rootfs: {status.stderr}")
            return None

        await run_command_async(
            "mv",
            str(tmp_squash),
            str(self.extracted_iso_dir / "pve-base.squashfs"),
            check=True,
        )

        # 13. Repack entire ISO

        await on_update(16, "Repacking modified ISO...")
        self.LOGGER.info(f"Repacking modified ISO with xorriso...: source {self.extracted_iso_dir} output {out}")
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
                candidates.extend(repacked_dir.glob("*.iso"))  # type: ignore
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
        self.LOGGER.info(
            {
                "base_iso_path": str(self.base_iso.iso_path),
                "work_dir": str(self.work_dir),
                "moved_from": str(src),
                "final_iso_dir": str(target_dir),
                "final_iso_path": str(dst),
            }
        )
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
