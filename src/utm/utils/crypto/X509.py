from typing import Any
from pathlib import Path
from cryptography import x509
from argparse import ArgumentParser
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes, serialization
from utm.utils.utils import get_local_ip


SAFE_PC_CERT_DEFAULTS: dict[str, Any] = {
    "cert_dir": Path(__file__).resolve().parents[4] / "certs",
    "name_prefix": "safe-pc-",
    "country": "US",
    "state": "AZ",
    "locality": "Tuscon",
    "organization": "SAFE-PC",
    "common_name": get_local_ip(),
    "alt_names": None,
    "days_valid": 365,
    "gen_if_exists": False,
}


def generate_self_signed_cert(**kwargs: Any) -> tuple[Path, Path]:
    """
    Generate a self-signed ECDSA certificate and private key.

    Args:
        kwargs: Dictionary of parameters. Uses SAFE_PC_CERT_DEFAULTS for missing keys.
        kwargs keys:
            cert_dir (Path): Directory to save the cert and key.
            name_prefix (str): Prefix for cert/key filenames.
            country (str): Country code (2-letter).
            state (str): State or province.
            locality (str): Locality or city.
            organization (str): Organization name.
            common_name (str): Common name, e.g. hostname or IP.
            alt_names (list[str]): Subject Alternative Names (list of DNS names).
            days_valid (int): Validity period in days.
            gen_if_exists (bool): If True, generates new cert even if one exists.

    Output:
        Writes {cert_dir}/{name_prefix}key.pem and {cert_dir}/{name_prefix}cert.pem
    """

    params: dict[str, Any] = {**SAFE_PC_CERT_DEFAULTS, **kwargs}

    cert_dir = Path(params["cert_dir"])
    name_prefix = params["name_prefix"]
    country = params["country"]
    state = params["state"]
    locality = params["locality"]
    organization = params["organization"]
    common_name = params["common_name"]
    alt_names = params["alt_names"]
    days_valid = params["days_valid"]
    gen_if_exists = params["gen_if_exists"]

    if not cert_dir.exists():
        cert_dir.mkdir(parents=True, exist_ok=False)

        cert_dir.chmod(0o700)

    private_key = ec.generate_private_key(ec.SECP256R1())

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, country),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
            x509.NameAttribute(NameOID.LOCALITY_NAME, locality),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )

    if alt_names is None:
        alt_names = [common_name]
    san = x509.SubjectAlternativeName([x509.DNSName(name) for name in alt_names])

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

    key_path = cert_dir / f"{name_prefix}key.pem"
    cert_path = cert_dir / f"{name_prefix}cert.pem"

    if not gen_if_exists and key_path.exists() and cert_path.exists():
        return key_path, cert_path

    count = 1
    while key_path.exists() or cert_path.exists():
        key_path = cert_dir / f"{name_prefix}key({count}).pem"
        cert_path = cert_dir / f"{name_prefix}cert({count}).pem"
        count += 1

    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    key_path.chmod(0o600)

    return key_path, cert_path


def main():

    parser = ArgumentParser(
        description="Generate a self-signed ECDSA certificate and private key."
    )
    ip = SAFE_PC_CERT_DEFAULTS["common_name"]
    parser.add_argument(
        "--cert_dir",
        type=Path,
        default=SAFE_PC_CERT_DEFAULTS["cert_dir"],
        help=f"Directory to save the cert and key (default: {SAFE_PC_CERT_DEFAULTS['cert_dir']}).",
    )
    parser.add_argument(
        "--name_prefix",
        type=str,
        default=SAFE_PC_CERT_DEFAULTS["name_prefix"],
        help=f"Prefix for cert/key filenames (default: {SAFE_PC_CERT_DEFAULTS['name_prefix']}).",
    )
    parser.add_argument(
        "--country",
        type=str,
        default=SAFE_PC_CERT_DEFAULTS["country"],
        help=f"Country code (default: {SAFE_PC_CERT_DEFAULTS['country']}).",
    )
    parser.add_argument(
        "--state",
        type=str,
        default=SAFE_PC_CERT_DEFAULTS["state"],
        help=f"State or province (default: {SAFE_PC_CERT_DEFAULTS['state']}).",
    )
    parser.add_argument(
        "--locality",
        type=str,
        default=SAFE_PC_CERT_DEFAULTS["locality"],
        help=f"Locality or city (default: {SAFE_PC_CERT_DEFAULTS['locality']}).",
    )
    parser.add_argument(
        "--organization",
        type=str,
        default=SAFE_PC_CERT_DEFAULTS["organization"],
        help=f"Organization name (default: {SAFE_PC_CERT_DEFAULTS['organization']}).",
    )
    parser.add_argument(
        "--common_name",
        type=str,
        default=f"{ip}",
        help=f"Common name, e.g. hostname or IP (default: {ip}).",
    )
    parser.add_argument(
        "--alt_names",
        nargs="*",
        default=SAFE_PC_CERT_DEFAULTS["alt_names"],
        help="Subject Alternative Names (space-separated list).",
    )
    parser.add_argument(
        "--days_valid",
        type=int,
        default=SAFE_PC_CERT_DEFAULTS["days_valid"],
        help=f"Validity period in days (default: {SAFE_PC_CERT_DEFAULTS['days_valid']}).",
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
    print(f"Successfully generated self-signed certificate and key for host: {ip}")
    print(f"  Generated key:  {key_path}")
    print(f"  Generated cert: {cert_path}")


if __name__ == "__main__":
    main()
