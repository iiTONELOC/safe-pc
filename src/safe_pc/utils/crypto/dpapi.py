from pathlib import Path
from cryptography.hazmat.primitives import serialization
from win32crypt import CryptProtectData, CryptUnprotectData


def write_dpapi_protected_key(private_key, key_path: Path):
    """
    Exports a private key as an unencrypted PEM, protects it using Windows DPAPI (user scope),
    and writes the protected bytes to the specified file path.
    Args:
        private_key: The private key object to export and protect.
        key_path (Path): The file path where the DPAPI-protected key will be written.
    Raises:
        Any exceptions raised during serialization, DPAPI protection, or file writing.
    """

    # Export as unencrypted PEM
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Protect with DPAPI (user scope)
    protected_bytes = CryptProtectData(pem_bytes, None, None, None, None, 0)

    key_path.write_bytes(protected_bytes)


def read_dpapi_protected_key(key_path: Path):
    """
    Reads a DPAPI-protected private key from the specified file path, unprotects it,
    and loads it as a private key object.
    Args:
        key_path (Path): The file path from which to read the DPAPI-protected key.
    Returns:
        The unprotected private key object.
    Raises:
        Any exceptions raised during file reading, DPAPI unprotection, or key loading.
    """
    protected_bytes = key_path.read_bytes()
    unprotected_bytes = CryptUnprotectData(protected_bytes, None, None, None, 0)[1]

    return serialization.load_pem_private_key(unprotected_bytes, password=None)
