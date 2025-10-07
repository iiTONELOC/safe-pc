"""
Description: This module is responsible for downloading the latest ISO for
Proxmox VE and verifying it hasn't been tampered with using via SHA-256 checksum.
"""

from re import match
from pathlib import Path
from typing import Callable
from httpx import AsyncClient
from logging import getLogger

from safe_pc.utils import IS_TESTING, compute_sha256
from safe_pc.proxmox_auto_installer.utils import handle_download

from bs4 import BeautifulSoup

LOGGER = getLogger(
    "capstone.proxmox_auto_installer.iso.downloader"
    if __name__ == "__main__"
    else __name__
)


def get_iso_folder_path(iso_name: str) -> Path:
    """Get the full path for the Proxmox ISO folder in the ISO directory.

    Args:
        iso_name (str): The name of the ISO file.

    Returns:
        Path: The full path to the ISOs folder.
    """
    DATA_DIR = (
        Path(__file__).resolve().parents[4] / "data"
        if not IS_TESTING()
        else Path(__file__).resolve().parents[4] / "tests"
    )
    ISO_DIR = DATA_DIR / "isos"

    for iso_dir in [DATA_DIR, ISO_DIR]:
        if not iso_dir.exists():
            iso_dir.mkdir(parents=True, exist_ok=True)

    return ISO_DIR / iso_name


def validate_iso_url(url: str) -> bool:
    """Validates the URL for the Proxmox ISO.

    Args:
        url (str): The ISO download URL to validate.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """

    pattern = r"^https://enterprise\.proxmox\.com/iso/proxmox-ve_[\d\.]+-.*\.iso$"
    return bool(match(pattern, url))


async def get_latest_proxmox_iso_url(
    url: str = "https://www.proxmox.com/en/downloads/proxmox-virtual-environment",
) -> tuple[str, str]:
    """Fetches the latest Proxmox VE ISO download URL and its SHA-256 checksum.

    Args:
        url (str, optional): The Proxmox downloads page URL. Defaults to the official
        Proxmox VE downloads page.
    Returns:
        tuple[str, str]: A tuple containing the ISO download URL and its SHA-256 checksum.
        This is empty i.e. ("", "") on failure.
    """

    # Fetch the Proxmox downloads page using requests
    try:
        async with AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.text
    except Exception as e:
        LOGGER.error(f"Failed to fetch Proxmox downloads page: {e}")
        return "", ""

    # parse the HTML to find the latest ISO link
    soup = BeautifulSoup(data, "html.parser")
    latest_downloads = soup.find("ul", class_="latest-downloads")
    second_li = latest_downloads.find_all("li")[1]  # type: ignore
    dl_btns = second_li.find("div", class_="download-entry-buttons")  # type: ignore
    iso_link = dl_btns.find("a", class_="button-primary")  # type: ignore

    # get the SHA-256 checksum
    div_container = second_li.find("div", class_="download-entry-info")  # type: ignore
    div_dl = div_container.find("dl")  # type: ignore
    sha_div = div_dl.find("div", class_="download-entry-shasum")  # type: ignore
    sha_dd = sha_div.find("dd")  # type: ignore
    sha_dd_code = sha_dd.find("code")  # type: ignore

    return iso_link["href"], sha_dd_code.text.strip()  # type: ignore


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


async def handle_iso_download(
    url: str, dest_path: Path, on_update: Callable | None = None
):
    """Downloads the ISO from the specified URL to the destination path and
    saves its SHA-256 checksum in a .sha256 file.
    Args:
        url (str): The URL to download the ISO from.
        dest_path (Path): The path to save the downloaded ISO file.
    """
    try:
        await handle_download(url, dest_path, on_update)
        sha256_hash = await compute_sha256(str(dest_path))
        dest_path.with_suffix(".sha256").write_text(sha256_hash)
    except Exception as e:
        LOGGER.error(f"Failed to download ISO: {e}")
        if dest_path.exists():
            dest_path.unlink()
        raise
