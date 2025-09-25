from getpass import getpass
from locale import getlocale
from logging import getLogger
from re import MULTILINE, sub
from capstone.utils import IS_VERBOSE
from capstone.utils.entropy import password_entropy
from capstone.utils.tzd import get_default_timezone
from capstone.proxmox.answer_file.constants import ALLOWED_KEYBOARDS
from tomlkit import dumps  # type: ignore[import]
from crypt_r import crypt, mksalt, METHOD_SHA512  # type: ignore[import]


LOGGER = getLogger(
    "capstone.proxmox.answer_file.utils" if __name__ == "__main__" else __name__
)


def _get_country(locale_str: str | None) -> str:
    if locale_str is None:
        locale_str = getlocale()[0]
    if locale_str is not None and locale_str != "C":
        print(f"Detected locale: {locale_str}")
        return locale_str.split("_")[-1].lower()
    return "us"


def _get_hashed_password(password: str) -> str:
    # Generate a password hash as expected by Proxmox/Linux
    # SHA-512 with a random salt
    salt = mksalt(METHOD_SHA512)  # type: ignore
    hashed_password = crypt(password, salt)  # type: ignore
    return hashed_password  # type: ignore


def gen_ans_file_with(mgmt_nic: str, disk: str) -> str:
    """
    Generates a Proxmox AnswerFile configuration as a TOML string, prompting the user for a strong root password.

    Args:
        mgmt_nic (str): The management network interface name to be used in the network configuration.
        disk (str): The disk identifier to be used in the disk setup configuration.
    Returns:
        str: The generated Proxmox AnswerFile as a TOML-formatted string.
    """

    # Generate a random password
    password = ""
    confirmed_pass = ""

    while password_entropy(password) < 60:
        password = getpass(
            prompt="Enter a strong root password (min entropy 60 bits) for Proxmox: ",
            stream=None,
        )

    while password != confirmed_pass:
        confirmed_pass = getpass(
            prompt="Confirm the root password: ",
            stream=None,
        )
        if password != confirmed_pass:
            print("Passwords do not match. Please try again.")

    hashed_password = _get_hashed_password(password)

    # clear the password variables
    confirmed_pass = ""
    password = ""

    # Get the system locale
    locale = getlocale()[0]
    country = _get_country(locale)
    keyboard = locale if locale in ALLOWED_KEYBOARDS else "en-us"
    timezone = get_default_timezone()

    if IS_VERBOSE():
        LOGGER.info("Generating Proxmox AnswerFile")
        LOGGER.info(f"Generated root password: {password}")
        LOGGER.info(f"Password entropy: {password_entropy(password):.2f} bits")

    ans_file_data: dict[str, dict[str, str | list[str]]] = {
        "global": {
            "keyboard": keyboard,
            "country": country,
            "timezone": timezone,
            "fqdn": "proxmox.lab.local",
            "mailto": "root@localhost",
            "root-password-hashed": hashed_password,
        },
        "network": {
            "source": "from-answer",
            "cidr": "10.0.4.254/24",
            "gateway": "10.0.4.1",
            "dns": "10.0.4.1",
            "filter.ID_NET_NAME_MAC": f"*{mgmt_nic}".replace(":", ""),
        },
        "disk-setup": {
            "filesystem": "zfs",
            "zfs.raid": "raid0",
            "disk-list": [f"{disk}"],
        },
    }

    if IS_VERBOSE():
        LOGGER.info("Generated AnswerFile:")
        LOGGER.info(dumps(ans_file_data))
    # Serialize to TOML and remove quotes around keys
    toml_str = dumps(ans_file_data)
    # Remove double quotes around keys at the start of lines
    toml_str = sub(r'^"([^"]+)"\s*=', r"\1 =", toml_str, flags=MULTILINE)
    return toml_str
