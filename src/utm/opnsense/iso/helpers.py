import re
from pathlib import Path
from httpx import AsyncClient
from logging import getLogger
from asyncio import gather as asyncio_gather
from secrets import choice as random_choice_secure
from utm.opnsense.iso.constants import OpnSenseConstants
from utm.utils import (
    is_testing,
    is_production,
    reach_consensus,
    validate_sha256,
    fetch_text_from_url,
    get_current_tz_utc_off_hrs,
)


from bs4 import BeautifulSoup

LOGGER = getLogger(__name__)


def get_closest_mirror() -> str:
    """Get the closest mirror for downloading OPNSense ISOs.

    Returns:
        str: The URL of the closest mirror.
    """
    # we don't really care about daylight savings time changes, just the rough offset
    PST_OFFSET = -8  # UTC-8
    EST_OFFSET = -5  # UTC-5
    current_offset = get_current_tz_utc_off_hrs()

    try:
        east_mirror, west_mirror = OpnSenseConstants.RELEASES[OpnSenseConstants.CURRENT_VERSION][1]
    except KeyError:
        raise KeyError(
            "Unsupported OPNSense version! Please update the OpnSenseConstants class or\
                downgrade to a supported version."
        )

    # return what ever is closer on number line, if equal, flip a coin
    if abs(current_offset - PST_OFFSET) < abs(current_offset - EST_OFFSET):
        return west_mirror
    elif abs(current_offset - PST_OFFSET) > abs(current_offset - EST_OFFSET):
        return east_mirror
    else:
        return random_choice_secure([east_mirror, west_mirror])


def extract_public_key_from_text(text: str) -> str:
    """Extracts the public key from the given text.

    Args:
        text (str): The text containing the public key.
    Returns:
        str: The extracted public key.
    """
    START = "-----BEGIN PUBLIC KEY-----"
    END = "-----END PUBLIC KEY-----"

    start_index = text.find(START)
    end_index = text.find(END, start_index) + len(END)

    if start_index == -1 or end_index == -1:
        raise ValueError("Public key not found in the provided text.")

    return text[start_index:end_index]


def extract_sha256_from_text(text: str, version: str) -> str:
    """Extracts the SHA256 hash for the specified version from the given text."""
    match = re.search(OpnSenseConstants.VERSION_HASH, text)
    if not match:
        raise ValueError(f"SHA256 hash for version {version} not found in the provided text.")
    return match.group(1)


async def extract_pub_key_from_mirror(mirror: str = OpnSenseConstants.PUB_KEY_MIRROR) -> str:
    """Fetches the public key from the OPNSense mirror.

    Returns:
        str: The public key as a string. Empty string on failure.

    Note:
        The mirror only lists the public key, not the SHA256 hashes.
    """
    try:
        async with AsyncClient() as client:
            response = await client.get(mirror)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            pub_key = extract_public_key_from_text(soup.get_text()) if soup else ""
            return pub_key
    except Exception as e:
        LOGGER.error(f"Failed to fetch public key from mirror: {e}")
        return ""


async def get_pub_key_and_hash(url: str, version: str) -> tuple[str, str]:
    """Get the public key and SHA256 hash for a given OPNSense version.

    Args:
        url (str): The URL of the page containing the public key and SHA256 hash.
    Returns:
        tuple[str, str]: A tuple containing the public key and SHA256 hash. Empty strings on failure.
    """
    try:

        txt = await fetch_text_from_url(url)
        pub_key = extract_public_key_from_text(txt)
        # replace ALL <brs> with newlines to ensure proper formatting
        pub_key = re.sub(r"<br\s*/?>", "\n", pub_key)
        # replace any \n# or \n # with just \n to clean up any comment lines
        pub_key = re.sub(r"\n\s*#", "\n", pub_key)
        sha256_hash = extract_sha256_from_text(txt, version)
        return pub_key, sha256_hash
    except Exception as e:
        LOGGER.error(f"Failed to fetch public key and SHA256 hash: {e}")
        return "", ""


async def get_educated_authoritative_key_and_hash() -> tuple[str, str]:
    """
    Determine the most trustworthy OPNsense public key and SHA256 hash
    by cross-checking multiple sources. Requires majority (n-1, min 2) agreement.

    Returns:
        Tuple[str, str]: (public_key, sha256_hash)
        The SHA256 may be empty if consensus wasn't reached.
    """
    discovered_keys: list[str] = []
    discovered_hashes: list[str] = []

    # 1. Mirror (baseline)
    mirror_key: str = await extract_pub_key_from_mirror() or ""
    if mirror_key:
        discovered_keys.append(mirror_key)
    else:
        LOGGER.warning("Failed to fetch public key from mirror.")
        

    # 2. Other release URLs concurrently
    release_urls: list[str] = OpnSenseConstants.RELEASES[OpnSenseConstants.CURRENT_VERSION][0]
    
    results: list[tuple[str, str] | BaseException] = await asyncio_gather(
        *[get_pub_key_and_hash(url, OpnSenseConstants.CURRENT_VERSION) for url in release_urls],
        return_exceptions=True,
    )
    

    for res in results:
        if isinstance(res, Exception):
            continue
        pub_key, sha256_hash = res  # type: ignore
        if pub_key:
            discovered_keys.append(pub_key)  # type: ignore
        if sha256_hash:
            discovered_hashes.append(sha256_hash)  # type: ignore
            

    # 3. Reach consensus
    key: str = reach_consensus(discovered_keys)
    sha256: str = reach_consensus(discovered_hashes)

    if key and sha256:
        return key, sha256

    LOGGER.warning(
        "Consensus not reached for OPNsense key/hash. Falling back to mirror key. This is NOT secure and\
            you should NOT proceed!"
    )
    return mirror_key, ""


async def get_latest_opns_url_w_hash() -> tuple[str, str, str]:

    try:
        # Try to get a hash and public key
        key, sha256 = await get_educated_authoritative_key_and_hash()

        if not key and not sha256 or not validate_sha256(sha256):
            err_msg = "Failed to obtain authoritative public key and SHA256 hash."
            LOGGER.error(err_msg)
            raise ValueError(err_msg)

        url = get_closest_mirror()

        # from the mirror, we need to first check its list of hashes
        # if these are different or do not exist, we should not proceed
        sums_url = f"{url}/OPNsense-{OpnSenseConstants.CURRENT_VERSION}-checksums-amd64.sha256"

        # grab the public key from the mirror too, just to be sure
        mirror_listed_key = await extract_pub_key_from_mirror(f"{url}/OPNsense-{OpnSenseConstants.CURRENT_VERSION}.pub")

        if not mirror_listed_key or mirror_listed_key != key:
            err_msg = "Public key from mirror does not match authoritative key. Not proceeding."
            LOGGER.error(err_msg)
            raise ValueError(err_msg)

        # verify the hash from the mirror matches the 'authoritative' hash (Note: this does NOT verify the ISO itself)
        mirror_listed_hash = extract_sha256_from_text(
            await fetch_text_from_url(sums_url), OpnSenseConstants.CURRENT_VERSION
        )

        if (
            not mirror_listed_hash
            or not validate_sha256(mirror_listed_hash)
            or (mirror_listed_hash.lower() != sha256.lower())
        ):
            err_msg = "Hash from mirror does not match authoritative hash. Not proceeding."

            LOGGER.error(err_msg)
            raise ValueError(err_msg)

        iso_url = f"{url}/OPNsense-{OpnSenseConstants.CURRENT_VERSION}-dvd-amd64.iso.bz2"

        return iso_url, sha256, key
    except Exception as e:
        LOGGER.error(f"Error determining authoritative key/hash: {e}")
        return "", "", ""


def get_iso_folder_path(iso_name: str) -> Path:
    """Get the full path for the OPNSense ISO folder.

    Args:
        iso_name (str): The name of the ISO file.

    Returns: The full path to the ISOs folder depending on the environment.

    Side Effects: Creates the ISO directory if it does not exist.
    """

    iso_path = (
        OpnSenseConstants.ISO_DIR / iso_name if not is_production() else Path(__file__).resolve() / "iso" / iso_name
    )

    if is_testing():
        iso_path = Path(__file__).resolve().parents[3] / "tests" / "data" / "isos" / iso_name
    if not iso_path.parent.exists():
        iso_path.parent.mkdir(parents=True, exist_ok=True)
    return iso_path
