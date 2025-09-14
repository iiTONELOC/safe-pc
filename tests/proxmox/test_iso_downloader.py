"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 2025-09-13
Description: This module provides tests for the Proxmox ISO Downloader.
"""

from capstone.utils.crypto import validate_sha256
from capstone.proxmox.iso_downloader import get_latest_proxmox_iso_url, validate_iso_url


def test_get_latest_proxmox_iso_url():
    """
    Test verifies that get_latest_proxmox_iso_url correctly fetches the latest Proxmox
    VE ISO URL and its SHA-256 checksum.
    """
    url, sha256 = get_latest_proxmox_iso_url()
    assert validate_iso_url(url)
    assert validate_sha256(sha256)
