"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 09/13/2025
Description: This module is responsible for downloading the latest ISO for
Proxmox VE and verifying it hasn't been tampered with using via SHA-256 checksum.
"""

from re import match
from http import client
from logging import getLogger
from capstone.utils.logs import setup_logging

from bs4 import BeautifulSoup


logger = getLogger(
    "capstone.proxmox.iso_downloader" if __name__ == "__main__" else __name__
)

""" TODO:
    1. Download the latest Proxmox VE ISO from the official source.
    2. Verify the integrity of the downloaded ISO using SHA-256 checksum.
    3. Save the ISO to a specified directory for later use.
    4. Log all actions and any errors encountered during the process.
"""


def validate_iso_url(url: str) -> bool:
    """Validates the Proxmox VE ISO URL format.

    Args:
        url (str): The ISO download URL to validate.

    Returns:
        bool: True if the URL is valid, False otherwise.
    """

    pattern = r"^https://enterprise\.proxmox\.com/iso/proxmox-ve_[\d\.]+-.*\.iso$"
    return bool(match(pattern, url))


def get_latest_proxmox_iso_url() -> tuple[str, str]:
    """Fetches the latest Proxmox VE ISO download URL and its SHA-256 checksum.

    Returns:
        tuple[str, str]: A tuple containing the ISO download URL and its SHA-256 checksum.
        This is empty i.e. ("", "") on failure.
    """

    # Connect to the Proxmox downloads page
    conn = client.HTTPSConnection("www.proxmox.com")
    conn.request("GET", "/en/downloads/proxmox-virtual-environment")

    # get the response
    response = conn.getresponse()
    if response.status != 200:
        logger.error(f"Failed to fetch Proxmox downloads page: {response.status}")
        return "", ""
    data = response.read().decode("utf-8")

    # close the connection
    conn.close()

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


def main():
    setup_logging()
    logger.warning("ISO Downloader module is not yet implemented.")


if __name__ == "__main__":
    main()
