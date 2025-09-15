"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 2025-09-13
Description: This module provides tests for the Proxmox ISO Downloader.
"""

import pytest
import tempfile
from pathlib import Path
from shutil import rmtree
from capstone.utils.crypto import validate_sha256
from capstone.proxmox.iso_downloader import (
    get_latest_proxmox_iso_url,
    validate_iso_url,
    get_iso_folder_path,
    _validate_latest,  # type: ignore
    _need_to_download,  # type: ignore
    _handle_download,  # type: ignore
)


def test_get_latest_proxmox_iso_url():
    """
    Test verifies that get_latest_proxmox_iso_url correctly fetches the latest Proxmox
    VE ISO URL and its SHA-256 checksum.
    """
    url, sha256 = get_latest_proxmox_iso_url()
    assert validate_iso_url(url)
    assert validate_sha256(sha256)

    # ensure that errors are handled gracefully

    url, sha256 = get_latest_proxmox_iso_url("invalid_url")

    assert url == ""
    assert sha256 == ""


def test_get_iso_folder_path():
    """
    Test verifies that get_iso_folder_path returns the correct path for a given ISO name.
    """
    iso_name = "proxmox-ve_"
    path = get_iso_folder_path(iso_name)
    assert iso_name in path.name
    assert path.parent.name == "isos"

    # delete the created directory
    if path.parent.exists():
        rmtree(path.parent)

    # get the path again to ensure it recreates the directory
    path = get_iso_folder_path(iso_name)
    assert path.parent.exists()
    assert path.name == iso_name


def test_validate_latest():
    """
    Test verifies that _validate_latest correctly validates the ISO URL and SHA-256 checksum.
    """
    valid_url = "https://enterprise.proxmox.com/iso/proxmox-ve_8.0-1.iso"
    valid_sha256 = "228f948ae696f2448460443f4b619157cab78ee69802acc0d06761ebd4f51c3e"
    assert _validate_latest(valid_url, valid_sha256)
    assert not _validate_latest("invalid_url", valid_sha256)
    assert not _validate_latest(valid_url, "invalid_sha256")
    assert not _validate_latest("invalid_url", "invalid_sha256")
    assert not _validate_latest("", "")


def test_need_to_download():
    valid_sha = "228f948ae696f2448460443f4b619157cab78ee69802acc0d06761ebd4f51c3e"

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        iso_file = tmpdir / "test.iso"
        sha_file = iso_file / f"{iso_file.name}.sha256"

        # Case 1: ISO does not exist
        assert _need_to_download(iso_file, valid_sha)

        # Case 2: ISO exists but no .sha256 file
        iso_file.touch()
        assert _need_to_download(iso_file, valid_sha)

        # Case 3: ISO exists with matching .sha256
        sha_file.parent.mkdir(parents=True, exist_ok=True)
        sha_file.write_text(valid_sha.lower())
        assert not _need_to_download(iso_file, valid_sha)

        # Case 4: ISO exists with mismatching .sha256
        sha_file.write_text("deadbeef")
        assert _need_to_download(iso_file, valid_sha)

        # Case 5: Case-insensitivity of hash
        sha_file.write_text(valid_sha.upper())
        assert not _need_to_download(iso_file, valid_sha.lower())


def test_handle_download(monkeypatch: pytest.MonkeyPatch) -> None:
    import capstone.proxmox.iso_downloader as iso_downloader

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir: Path = Path(tmp)
        dest: Path = tmpdir / "file.iso"

        # --- Case 1: Successful download ---
        called: dict[str, object] = {}

        def fake_download(url: str, path: Path) -> None:
            called["download"] = (url, path)
            path.write_text("ISO DATA")

        def fake_sha256(path: str) -> str:
            called["sha"] = path
            return "abc123"

        monkeypatch.setattr(iso_downloader, "handle_download", fake_download)
        monkeypatch.setattr(iso_downloader, "compute_sha256", fake_sha256)

        iso_downloader._handle_download("http://example.com/file.iso", dest)  # type: ignore

        assert called["download"][0] == "http://example.com/file.iso"  # type: ignore
        assert called["download"][1] == dest  # type: ignore
        assert called["sha"] == str(dest)
        assert dest.with_suffix(".sha256").read_text() == "abc123"

        # --- Case 2: Download failure ---
        def bad_download(url: str, path: Path) -> None:
            path.write_text("BROKEN DATA")
            raise RuntimeError("network fail")

        monkeypatch.setattr(iso_downloader, "handle_download", bad_download)

        with pytest.raises(RuntimeError):
            iso_downloader._handle_download("http://bad.com/file.iso", dest)  # type: ignore

        # The dest file should have been cleaned up
        assert not dest.exists()
