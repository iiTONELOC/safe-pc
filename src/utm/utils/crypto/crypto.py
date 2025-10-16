"""
Description: This module provides reusable async cryptographic utilities.
"""

import asyncio, base64, hashlib
from re import match
from pathlib import Path
from logging import getLogger
from hashlib import sha256, sha512
from utm.utils.utils import is_verbose
from aiofiles import open as aiofiles_open

CHUNK_SIZE = 8192
LOGGER = getLogger(__name__)


async def compute_sha256(for_file_path: str) -> str:
    """
    Asynchronously compute the SHA-256 hash of a file.

    Args:
        for_file_path: Path to the file.

    Returns:
        The SHA-256 hash as a hexadecimal string.
    """
    hash_sha256 = sha256()
    try:
        async with aiofiles_open(for_file_path, "rb") as f:
            while True:
                chunk = await f.read(CHUNK_SIZE)
                if not chunk:
                    break
                hash_sha256.update(chunk)
        if is_verbose():
            LOGGER.info(f"SHA-256 for {for_file_path}: {hash_sha256.hexdigest()}")
        return hash_sha256.hexdigest()
    except FileNotFoundError:
        LOGGER.error(f"File not found: {for_file_path}")
        raise
    except Exception as e:
        LOGGER.error(f"Error computing SHA-256 for {for_file_path}: {e}")
        raise


async def verify_sha256(for_file_path: str, expected_hash: str) -> bool:
    """
    Verify the SHA-256 hash of a file against an expected hash.

    Args:
        for_file_path: Path to the file.
        expected_hash: The expected SHA-256 hash as a hexadecimal string.
    Returns:
        True if the computed hash matches the expected hash, False otherwise.
    """

    try:
        # get the computed hash
        computed_hash = await compute_sha256(for_file_path)
        # normalize to lowercase for comparison
        if computed_hash.lower() == expected_hash.lower():
            if is_verbose():
                LOGGER.info(f"Hash match for {for_file_path}")
            return True
        else:
            LOGGER.warning(
                f"Hash mismatch for {for_file_path}: expected {expected_hash}, got {computed_hash}"
            )
            return False
    except Exception as e:
        LOGGER.error(f"Error verifying SHA-256 for {for_file_path}: {e}")
        return False


def validate_sha256(sha256: str) -> bool:
    """Validates the SHA-256 checksum format.

    Args:
        sha256 (str): The SHA-256 checksum to validate.

    Returns:
        bool: True if the checksum is valid, False otherwise.
    """

    pattern = r"^[a-fA-F0-9]{64}$"
    return bool(match(pattern, sha256))


async def compute_sha512(for_file_path: str) -> str:
    """
    Asynchronously compute the SHA-512 hash of a file.

    Args:
        for_file_path: Path to the file.
    Returns:
        The SHA-512 hash as a hexadecimal string.
    """

    hash_sha512 = sha512()
    try:
        async with aiofiles_open(for_file_path, "rb") as f:
            while True:
                chunk = await f.read(CHUNK_SIZE)
                if not chunk:
                    break
                hash_sha512.update(chunk)
        if is_verbose():
            LOGGER.info(f"SHA-512 for {for_file_path}: {hash_sha512.hexdigest()}")
        return hash_sha512.hexdigest()
    except FileNotFoundError:
        LOGGER.error(f"File not found: {for_file_path}")
        raise
    except Exception as e:
        LOGGER.error(f"Error computing SHA-512 for {for_file_path}: {e}")
        raise


async def verify_sha512(for_file_path: str, expected_hash: str) -> bool:
    """
    Verify the SHA-512 hash of a file against an expected hash.

    Args:
        for_file_path: Path to the file.
        expected_hash: The expected SHA-512 hash as a hexadecimal string.
    Returns:
        True if the computed hash matches the expected hash, False otherwise.
    """

    try:
        # get the computed hash
        computed_hash = await compute_sha512(for_file_path)
        # normalize to lowercase for comparison
        if computed_hash.lower() == expected_hash.lower():
            if is_verbose():
                LOGGER.info(f"Hash match for {for_file_path}")
            return True
        else:
            LOGGER.warning(
                f"Hash mismatch for {for_file_path}: expected {expected_hash}, got {computed_hash}"
            )
            return False
    except Exception as e:
        LOGGER.error(f"Error verifying SHA-512 for {for_file_path}: {e}")
        return False


def validate_sha512(sha512: str) -> bool:
    """Validates the SHA-512 checksum format.

    Args:
        sha512 (str): The SHA-512 checksum to validate.

    Returns:
        bool: True if the checksum is valid, False otherwise.
    """

    pattern = r"^[a-fA-F0-9]{128}$"
    return bool(match(pattern, sha512))


async def cert_sha256_fingerprint(path: str, colon: bool = True, upper: bool = True):
    """Return the SHA-256 fingerprint of a certificate file (PEM or DER)."""

    data = await asyncio.to_thread(Path(path).read_bytes)

    BEGIN = b"-----BEGIN CERTIFICATE-----"
    END = b"-----END CERTIFICATE-----"

    # If PEM, extract first cert block and decode to DER; else treat as DER
    if data.lstrip().startswith(BEGIN):
        i = data.find(BEGIN)
        j = data.find(END, i)
        if i < 0 or j < 0:
            raise ValueError("Invalid PEM certificate")
        b64 = b"".join(data[i + len(BEGIN) : j].split())
        der = base64.b64decode(b64, validate=False)
    else:
        der = data

    h = hashlib.sha256(der).hexdigest()
    if upper:
        h = h.upper()
    if colon:
        h = ":".join(h[i : i + 2] for i in range(0, len(h), 2))
    return h
