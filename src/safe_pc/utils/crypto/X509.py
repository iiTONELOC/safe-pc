from pathlib import Path
from cryptography import x509
from os import name as os_name
from argparse import ArgumentParser
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization


# if windows, import the required modules for setting file permissions
if os_name == "nt":
    from safe_pc.utils.crypto.dpapi import write_dpapi_protected_key
    import win32api
    import win32security
    import ntsecuritycon as con


def generate_self_signed_cert(
    cert_dir=Path(__file__).resolve().parents[4] / "certs",
    name_prefix="",
    country="US",
    state="AZ",
    locality="Tuscon",
    organization="SAFE-PC",
    common_name="127.0.0.1",
    alt_names=None,
    days_valid=365,
    gen_if_exists=False,
):
    """
    Generate a self-signed ECDSA certificate and private key.

    Args:
        cert_dir (str|Path): Directory to save the cert and key.
        name_prefix (str): Prefix for cert/key filenames.
        country (str): Country code (e.g., "US").
        state (str): State or province.
        locality (str): Locality or city.
        organization (str): Organization name.
        common_name (str): Common name (e.g., hostname or IP).
        alt_names (list[str]): Subject Alternative Names (DNS names).
        days_valid (int): Validity period in days.

    Output:
        Writes {cert_dir}/{name_prefix}key.pem and {cert_dir}/{name_prefix}cert.pem
    """

    cert_dir = Path(cert_dir)
    if not cert_dir.exists():

        # Create the certs directory if it doesn't exist
        cert_dir.mkdir(parents=True, exist_ok=False)

        # Harden permissions
        if os_name == "posix":
            cert_dir.chmod(0o700)
        elif os_name == "nt":
            _harden_windows_dir(cert_dir)

    # Generate ECDSA private key
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Subject/issuer info
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, locality),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    # SAN (fallback to CN if not provided)
    if alt_names is None:
        alt_names = [common_name]

    san = x509.SubjectAlternativeName([x509.DNSName(name) for name in alt_names])

    # Build cert
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=days_valid))
        .add_extension(san, critical=False)
        .sign(private_key, hashes.SHA256())
    )

    # Paths
    key_path = cert_dir / f"{name_prefix}key.pem"
    cert_path = cert_dir / f"{name_prefix}cert.pem"

    # if the files exist and we shouldn't generate new ones, return the existing paths
    if not gen_if_exists and key_path.exists() and cert_path.exists():
        return key_path, cert_path

    # check if the files already exist, if they do, count up the prefix
    count = 1
    while key_path.exists() or cert_path.exists():
        key_path = cert_dir / f"{name_prefix}key({count}).pem"
        cert_path = cert_dir / f"{name_prefix}cert({count}).pem"
        count += 1

    if os_name == "nt":
        # use DPAPI to protect the private key on Windows
        write_dpapi_protected_key(private_key, key_path)
    else:
        # Write private key - locked down permissions on non-Windows
        key_path.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Write cert
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    # Harden permissions on the key file
    if os_name == "posix":
        key_path.chmod(0o600)
    elif os_name == "nt":
        _harden_windows_file(key_path)

    return key_path, cert_path


def _harden_windows_dir(path: Path):
    """Restrict directory access to current user (Windows)."""
    username = win32api.GetUserName()
    user, _, _ = win32security.LookupAccountName("", username)

    sd = win32security.SECURITY_DESCRIPTOR()
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE | con.FILE_GENERIC_EXECUTE,
        user,
    )
    sd.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(
        str(path), win32security.DACL_SECURITY_INFORMATION, sd
    )


def _harden_windows_file(path: Path):
    """Restrict file access to current user (Windows)."""
    username = win32api.GetUserName()
    user, _, _ = win32security.LookupAccountName("", username)

    sd = win32security.SECURITY_DESCRIPTOR()
    dacl = win32security.ACL()
    dacl.AddAccessAllowedAce(
        win32security.ACL_REVISION,
        con.FILE_GENERIC_READ | con.FILE_GENERIC_WRITE,
        user,
    )
    sd.SetSecurityDescriptorDacl(1, dacl, 0)
    win32security.SetFileSecurity(
        str(path), win32security.DACL_SECURITY_INFORMATION, sd
    )


def main():
    parser = ArgumentParser(
        description="Generate a self-signed ECDSA certificate and private key."
    )
    parser.add_argument(
        "--cert_dir",
        type=Path,
        default=Path(__file__).resolve().parents[4] / "certs",
        help="Directory to save the cert and key (default: %(default)s).",
    )
    parser.add_argument(
        "--name_prefix", type=str, default="", help="Prefix for cert/key filenames."
    )
    parser.add_argument(
        "--country", type=str, default="US", help="Country code (default: US)."
    )
    parser.add_argument(
        "--state", type=str, default="AZ", help="State or province (default: AZ)."
    )
    parser.add_argument(
        "--locality",
        type=str,
        default="Tuscon",
        help="Locality or city (default: Tuscon).",
    )
    parser.add_argument(
        "--organization",
        type=str,
        default="SAFE-PC",
        help="Organization name (default: SAFE-PC).",
    )
    parser.add_argument(
        "--common_name",
        type=str,
        default="127.0.0.1",
        help="Common name, e.g. hostname or IP (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--alt_names",
        nargs="*",
        default=None,
        help="Subject Alternative Names (space-separated list).",
    )
    parser.add_argument(
        "--days_valid",
        type=int,
        default=365,
        help="Validity period in days (default: 365).",
    )
    parser.add_argument(
        "--gen_if_exists",
        action="store_true",
        help="Force generate new cert even if one exists.",
    )

    args = parser.parse_args()

    key_path, cert_path = generate_self_signed_cert(
        cert_dir=args.cert_dir,
        name_prefix=args.name_prefix,
        country=args.country,
        state=args.state,
        locality=args.locality,
        organization=args.organization,
        common_name=args.common_name,
        alt_names=args.alt_names,
        days_valid=args.days_valid,
        gen_if_exists=args.gen_if_exists,
    )

    print(f"Generated key:  {key_path}")
    print(f"Generated cert: {cert_path}")


if __name__ == "__main__":
    main()
