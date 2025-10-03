"""
Description: This module provides reusable cryptographic utilities.
"""

from logging import getLogger
from hashlib import sha256, sha512
from safe_pc.utils.utils import IS_VERBOSE


CHUNK_SIZE = 8192
logger = getLogger("capstone.utils.crypto" if __name__ == "__main__" else __name__)


def compute_sha256(for_file_path: str) -> str:
    """
    Compute the SHA-256 hash of a file.

    Args:
        for_file_path: Path to the file.

    Returns:
        The SHA-256 hash as a hexadecimal string.
    """
    hash_sha256 = sha256()
    try:
        with open(for_file_path, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                hash_sha256.update(chunk)
        if IS_VERBOSE():
            logger.info(f"SHA-256 for {for_file_path}: {hash_sha256.hexdigest()}")
        return hash_sha256.hexdigest()
    except FileNotFoundError:
        logger.error(f"File not found: {for_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error computing SHA-256 for {for_file_path}: {e}")
        raise


def verify_sha256(for_file_path: str, expected_hash: str) -> bool:
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
        computed_hash = compute_sha256(for_file_path)
        # normalize to lowercase for comparison
        if computed_hash.lower() == expected_hash.lower():
            if IS_VERBOSE():
                logger.info(f"Hash match for {for_file_path}")
            return True
        else:
            logger.warning(
                f"Hash mismatch for {for_file_path}: expected {expected_hash}, got {computed_hash}"
            )
            return False
    except Exception as e:
        logger.error(f"Error verifying SHA-256 for {for_file_path}: {e}")
        return False


def validate_sha256(sha256: str) -> bool:
    """Validates the SHA-256 checksum format.

    Args:
        sha256 (str): The SHA-256 checksum to validate.

    Returns:
        bool: True if the checksum is valid, False otherwise.
    """
    import re

    pattern = r"^[a-fA-F0-9]{64}$"
    return bool(re.match(pattern, sha256))


def compute_sha512(for_file_path: str) -> str:
    """
    Compute the SHA-512 hash of a file.

    Args:
        for_file_path: Path to the file.
    Returns:
        The SHA-512 hash as a hexadecimal string.
    """

    hash_sha512 = sha512()
    try:
        with open(for_file_path, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
                hash_sha512.update(chunk)
        if IS_VERBOSE():
            logger.info(f"SHA-512 for {for_file_path}: {hash_sha512.hexdigest()}")
        return hash_sha512.hexdigest()
    except FileNotFoundError:
        logger.error(f"File not found: {for_file_path}")
        raise
    except Exception as e:
        logger.error(f"Error computing SHA-512 for {for_file_path}: {e}")
        raise


def verify_sha512(for_file_path: str, expected_hash: str) -> bool:
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
        computed_hash = compute_sha512(for_file_path)
        # normalize to lowercase for comparison
        if computed_hash.lower() == expected_hash.lower():
            if IS_VERBOSE():
                logger.info(f"Hash match for {for_file_path}")
            return True
        else:
            logger.warning(
                f"Hash mismatch for {for_file_path}: expected {expected_hash}, got {computed_hash}"
            )
            return False
    except Exception as e:
        logger.error(f"Error verifying SHA-512 for {for_file_path}: {e}")
        return False


def validate_sha512(sha512: str) -> bool:
    """Validates the SHA-512 checksum format.

    Args:
        sha512 (str): The SHA-512 checksum to validate.

    Returns:
        bool: True if the checksum is valid, False otherwise.
    """
    import re

    pattern = r"^[a-fA-F0-9]{128}$"
    return bool(re.match(pattern, sha512))
