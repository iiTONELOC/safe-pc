"""
Description: This module is responsible for downloading the latest ISO for
Proxmox VE and verifying it hasn't been tampered with using via SHA-256 checksum.
"""

from re import match
from pathlib import Path
from httpx import AsyncClient
from logging import getLogger

from utm.utils import is_testing

from bs4 import BeautifulSoup

LOGGER = getLogger(__name__)


def get_iso_folder_path(iso_name: str) -> Path:
    """Get the full path for the Proxmox ISO folder in the ISO directory.

    Args:
        iso_name (str): The name of the ISO file.

    Returns:
        Path: The full path to the ISOs folder.
    """
    DATA_DIR = (
        Path(__file__).resolve().parents[3] / "data"
        if not is_testing()
        else Path(__file__).resolve().parents[3] / "tests"
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


async def get_latest_prox_url_w_hash(
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
