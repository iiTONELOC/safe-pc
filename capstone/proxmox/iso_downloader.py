"""
Description: This module is responsible for downloading the latest ISO for
Proxmox VE and verifying it hasn't been tampered with using via SHA-256 checksum.
"""

from re import match
from pathlib import Path
from requests import get
from logging import getLogger

from capstone.utils import IS_TESTING
from capstone.utils.logs import setup_logging
from capstone.utils.downloader import handle_download
from capstone.utils.crypto import compute_sha256, validate_sha256, verify_sha256

from bs4 import BeautifulSoup


LOGGER = getLogger(
    "capstone.proxmox.iso_downloader" if __name__ == "__main__" else __name__
)


def get_iso_folder_path(iso_name: str) -> Path:
    """Get the full path for the Proxmox ISO folder in the ISO directory.

    Args:
        iso_name (str): The name of the ISO file.

    Returns:
        Path: The full path to the ISOs folder.
    """
    DATA_DIR = (
        Path(__file__).resolve().parents[2] / "data"
        if not IS_TESTING()
        else Path(__file__).resolve().parents[2] / "tests"
    )
    ISO_DIR = DATA_DIR / "isos"

    for iso_dir in [DATA_DIR, ISO_DIR]:
        if not iso_dir.exists():
            iso_dir.mkdir(parents=True, exist_ok=True)

    return ISO_DIR / iso_name


def validate_iso_url(url: str) -> bool:
    """Validates the Proxmox VE ISO URL format.

    Args:
        url (str): The ISO download URL to validate.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """

    pattern = r"^https://enterprise\.proxmox\.com/iso/proxmox-ve_[\d\.]+-.*\.iso$"
    return bool(match(pattern, url))


def get_latest_proxmox_iso_url(
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
        response = get(url, timeout=10)
        response.raise_for_status()
    except Exception as e:
        LOGGER.error(f"Failed to fetch Proxmox downloads page: {e}")
        return "", ""
    data = response.text

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


def _validate_latest(url: str, sha256: str) -> bool:
    """Validates the latest Proxmox VE ISO URL and SHA-256 checksum.

    Args:
        url (str): The ISO download URL to validate.
        sha256 (str): The SHA-256 checksum to validate.

    Returns:
        bool: True if both the URL and checksum are valid, False otherwise.
    """
    is_url_valid = validate_iso_url(url)
    is_sha256_valid = validate_sha256(sha256)

    if not is_url_valid:
        LOGGER.error(f"Invalid Proxmox VE ISO URL: {url}")
    if not is_sha256_valid:
        LOGGER.error(f"Invalid SHA-256 checksum format: {sha256}")

    return is_url_valid and is_sha256_valid


def _need_to_download(iso_path: Path, expected_sha256: str) -> bool:
    """Determines if the ISO needs to be downloaded based on its existence and SHA-256 checksum.

    Args:
        iso_path (Path): The path to the ISO file.
        expected_sha256 (str): The expected SHA-256 checksum.

    Returns:
        bool: True if the ISO needs to be downloaded, False otherwise.
    """
    if not iso_path.exists():
        LOGGER.info(f"ISO does not exist at {iso_path}, need to download.")
        # create the directory if it doesn't exist
        if not iso_path.exists():
            iso_path.mkdir(parents=True, exist_ok=True)
        return True

    LOGGER.info(f"ISO already exists at {iso_path}, verifying SHA-256...")
    hash_file = iso_path / f"{iso_path.name}.sha256"
    existing_hash = hash_file.read_text().strip() if hash_file.exists() else ""

    if existing_hash.lower() == expected_sha256.lower():
        return False
    else:
        LOGGER.warning("Existing ISO is invalid, need to re-download.")
        return True


def _handle_download(url: str, dest_path: Path):
    """Handles the downloading of the ISO file from the given URL to the destination path.

    Args:
        url (str): The URL to download the ISO from.
        dest_path (Path): The path to save the downloaded ISO file.
    """
    try:
        handle_download(url, dest_path)
        # Compute hash efficiently using buffered read
        sha256_hash = compute_sha256(str(dest_path))
        dest_path.with_suffix(".sha256").write_text(sha256_hash)
    except Exception as e:
        LOGGER.error(f"Failed to download ISO: {e}")
        if dest_path.exists():
            dest_path.unlink()
        raise


def main():  # pragma: no cover start
    """Main Entry point for the Proxmox ISO downloader module."""
    setup_logging()

    # 1. get the url and hash for the latest iso
    latest_url, latest_sha256 = get_latest_proxmox_iso_url()

    # verify the url and sha are valid
    if not _validate_latest(latest_url, latest_sha256):
        LOGGER.error(
            "Failed to validate the latest Proxmox VE ISO URL or SHA-256 checksum."
        )
        return

    # 2. Check if we need to download the iso or if we already have it
    iso_name = latest_url.split("/")[-1].replace(".iso", "")
    have_to_download = _need_to_download(get_iso_folder_path(iso_name), latest_sha256)

    # 3. Download only if needed
    if not have_to_download:
        LOGGER.info("No download needed.")
        return

    LOGGER.info(f"Please Wait. Downloading Proxmox VE ISO from {latest_url}...")
    iso_file_path = get_iso_folder_path(iso_name) / f"{iso_name}.iso"
    _handle_download(latest_url, iso_file_path)

    # 4. Verify the download
    if verify_sha256(str(iso_file_path), latest_sha256):
        LOGGER.info("Downloaded ISO is valid.")
    else:
        LOGGER.error("Downloaded ISO is invalid, removing file.")
        iso_file_path.unlink()
        return

    LOGGER.info(f"{iso_name} download and verification complete.")


if __name__ == "__main__":
    main()
