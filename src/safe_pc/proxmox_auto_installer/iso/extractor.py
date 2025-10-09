from pathlib import Path
from logging import getLogger
from asyncio import create_subprocess_exec, subprocess
from re import L

# extraction logic for Windows (requires different tools than Unix/Linux)

LOGGER = getLogger(
    "capstone.proxmox_auto_installer.iso.extractor"
    if __name__ == "__main__"
    else __name__
)


OSCDIMG_PATH = r"C:\Program Files (x86)\Windows Kits\10\Assessment and Deployment Kit\Deployment Tools\amd64\Oscdimg\oscdimg.exe"


async def unpack_iso_7z(iso_path: Path, dest_path: Path) -> bool:
    """
    Unpacks the ISO file to the specified directory.

    Args:
        iso_path (Path): The path to the ISO file.
        dest_path (Path): The directory where the ISO contents will be extracted.

    Raises:
        FileNotFoundError: If the ISO file does not exist.
        RuntimeError: If the extraction fails.
    """
    if not iso_path.exists():
        raise FileNotFoundError(f"ISO file not found: {iso_path}")

    dest_path.mkdir(parents=True, exist_ok=True)

    process = await create_subprocess_exec(
        r"C:\Program Files\7-Zip\7z.exe",
        "x",
        str(iso_path),
        f"-o{str(dest_path)}",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_data, stderr_data = await process.communicate()

    LOGGER.info(f"7z stdout (truncated): {stdout_data[:500].decode(errors='ignore')}")
    LOGGER.info(f"7z stderr (truncated): {stderr_data[:500].decode(errors='ignore')}")
    LOGGER.info(f"7z return code: {process.returncode}")
    if process.returncode not in (0, 2):
        LOGGER.error(f"7z extraction failed with code {process.returncode}")
        return False
    else:
        if process.returncode == 2:
            LOGGER.warning(
                "7z returned code 2 (dangerous link paths ignored), treating as success"
            )
        return True


async def repack_iso_oscdimg(source_dir: Path, output_iso: Path) -> bool:
    """
    Use Microsoft's oscdimg.exe (from Windows ADK) to build a bootable ISO on Windows.
    Note: oscdimg must be installed separately as part of the Windows ADK.
    """
    # Path to boot catalog in unpacked Proxmox ISO
    boot_catalog = source_dir / "boot" / "grub" / "i386-pc" / "eltorito.img"

    if not boot_catalog.exists():
        LOGGER.error(f"Boot catalog not found at expected path: {boot_catalog}")
        return False

    LOGGER.info(f"Repacking ISO with oscdimg from {source_dir} to {output_iso}")

    process = await create_subprocess_exec(
        OSCDIMG_PATH,
        "-n",  # Enable long file names (Joliet)
        "-m",  # Ignore max size check
        "-b" + f"{boot_catalog}",
        str(source_dir),
        str(output_iso),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout_data, stderr_data = await process.communicate()
    LOGGER.info(f"oscdimg stdout: {stdout_data.decode(errors='ignore')}")
    LOGGER.info(f"oscdimg stderr: {stderr_data.decode(errors='ignore')}")
    LOGGER.info(f"oscdimg return code: {process.returncode}")

    return process.returncode == 0
