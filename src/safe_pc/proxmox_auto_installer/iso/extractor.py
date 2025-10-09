import glob
from pathlib import Path
from logging import getLogger
from asyncio import create_subprocess_exec, subprocess

LOGGER = getLogger(
    "capstone.proxmox_auto_installer.iso.extractor"
    if __name__ == "__main__"
    else __name__
)


async def unpack_iso_7z(iso_path: Path, dest_path: Path) -> None:
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
    _, stderr = await process.communicate()
    LOGGER.debug(f"7z output: {stderr.decode().strip()}")
    if process.returncode != 0:
        raise RuntimeError(f"Failed to extract ISO: {stderr.decode().strip()}")


async def repack_iso_7z(source_dir: Path, output_iso: Path) -> None:
    if not source_dir.exists() or not source_dir.is_dir():
        raise FileNotFoundError(
            f"Source directory not found or is not a directory: {source_dir}"
        )

    # Expand files manually
    files = glob.glob(str(source_dir / "*"))

    if not files:
        raise RuntimeError(f"No files found to pack in {source_dir}")

    process = await create_subprocess_exec(
        r"C:\Program Files\7-Zip\7z.exe",
        "a",
        "-tiso",
        str(output_iso),
        *files,  # <-- expanded list
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    LOGGER.debug(f"7z output: {stderr.decode().strip()}")
    if process.returncode != 0:
        raise RuntimeError(f"Failed to create ISO: {stderr.decode().strip()}")
