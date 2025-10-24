from os import getenv
from pathlib import Path

from utm.__main__ import is_testing, is_production


def get_opns_iso_dir() -> Path:
    if is_testing():
        base_dir = Path(__file__).resolve().parents[4] / "tests" / "data" / "isos" / "opnsense"
    elif is_production():
        # production uses proxmox location for isos
        base_dir = Path("/var/lib/vz/template/iso/")
    else:
        base_dir = Path(__file__).resolve().parents[4] / "data" / "isos" / "opnsense"

    if not base_dir.exists():
        base_dir.mkdir(parents=True, exist_ok=True)

    return base_dir


class OpnSenseConstants:
    CURRENT_VERSION = getenv("SAFE_PC_OPNSENSE_VERSION") or "25.7"
    ISO_DIR = get_opns_iso_dir()
    PUB_KEY_MIRROR = "https://pkg.opnsense.org/releases/mirror/README"  # not trusted, just for reference
    # NOSONAR TODO: ONLY support the latest 2 releases at any time (hardcoded this for now)
    RELEASES = {
        "25.7": [
            [  # contains Public Key AND SHA256 hashes - not trusted either, but more trusted than the mirror
                # above (all three should match)
                "https://forum.opnsense.org/index.php?topic=48072.0",
                f"https://raw.githubusercontent.com/opnsense/changelog/refs/heads/master/community/{CURRENT_VERSION}/{CURRENT_VERSION}",
            ],  # mirrors for download (also have sha256 hashes and even public key)
            [
                "https://mirror.wdc1.us.leaseweb.net/opnsense/releases/25.7/",  # east coast US
                "https://mirror.sfo12.us.leaseweb.net/opnsense/releases/25.7/",  # west coast US
            ],
        ]
    }  # needs to be updated with each release
    VERSION_HASH = rf"SHA256\s*\(OPNsense-{CURRENT_VERSION}-serial-amd64\.img\.bz2\)\s*=\s*([a-fA-F0-9]{{64}})"
