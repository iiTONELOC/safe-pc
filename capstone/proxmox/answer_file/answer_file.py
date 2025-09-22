"""
This module defines the data model for the Proxmox VE auto-installation answer file,
using Pydantic for validation and serialization.

The definitions closely follow the
specifications outlined in the Proxmox documentation:
`[Proxmox Answer File Format](https://pve.proxmox.com/wiki/Automated_Installation#Answer_File_Format_2)`
"""

from pathlib import Path
from typing import Annotated
from re import match, search
from collections.abc import Mapping
from tomllib import load as toml_load
from capstone.utils.crypto import validate_sha512
from capstone.utils.entropy import password_entropy
from ipaddress import IPv4Interface, IPv6Interface, IPv4Address, IPv6Address
from capstone.proxmox.answer_file.constants import (
    ALLOWED_KEYBOARDS,
    ALLOWED_REBOOT_MODES,
    ALLOWED_NETWORK_SOURCES,
    ALLOWED_FILESYSTEMS,
    ALLOWED_FILTER_MATCH,
    ALLOWED_ZFS_RAID,
    ALLOWED_ZFS_CHECKSUM,
    ALLOWED_ZFS_COMPRESS,
    ALLOWED_BTRFS_RAID,
    ALLOWED_BTRFS_COMPRESS,
    ALLOWED_FIRST_BOOT_SOURCES,
    ALLOWED_FIRST_BOOT_ORDERING,
)
from tomlkit import dumps  # type: ignore[import]
from pydantic import (
    Field,
    HttpUrl,
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

# Type aliases
# ---------------------------------------------------------------------------------------

IPvAnyInterface = IPv4Interface | IPv6Interface
IPvAnyAddress = IPv4Address | IPv6Address

# PSEUDO Constants
PLACEHOLDER_PATTERN = r"\{\{[A-Za-z0-9_.-]+\}\}$"
Placeholder = Annotated[
    str, StringConstraints(pattern=PLACEHOLDER_PATTERN)
]  # a templated string


# Helpers
# ---------------------------------------------------------------------------------------


# Helper to identify placeholders
def _is_placeholder(value: str) -> bool:
    return bool(match(PLACEHOLDER_PATTERN, value))


# Helper to verify positive integer or placeholder
def _verify_positive_integer(
    value: int | Placeholder | None, field_name: str
) -> int | Placeholder | None:
    if isinstance(value, str) and _is_placeholder(value):
        return value  # allow placeholders
    elif isinstance(value, str):
        raise ValueError(f"{field_name} must be an integer or a placeholder")
    elif value is not None and value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    else:
        return value


# Classes
# ---------------------------------------------------------------------------------------


# FQDN (string OR DHCP-based object)
class FQDNFromDHCP(BaseModel):
    source: str | Placeholder
    domain: str | Placeholder | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("source")
    @classmethod
    def _must_be_from_dhcp(cls, value: str) -> str:
        if value != "from-dhcp" and not _is_placeholder(value):
            raise ValueError("fqdn.source must be 'from-dhcp'")
        return value

    # validate the domain if present
    @field_validator("domain")
    @classmethod
    def _domain_valid(cls, domain: str | None) -> str | None:
        if domain is not None and not _is_placeholder(domain):
            if len(domain) > 255:
                raise ValueError("domain must be less than 256 characters")
            if domain.endswith("."):
                domain = domain[:-1]  # strip trailing dot
            cls._validate_domain_labels(domain)
        return domain

    @staticmethod
    def _validate_domain_labels(domain: str) -> None:
        if _is_placeholder(domain):
            return
        labels = domain.split(".")
        for label in labels:
            if len(label) == 0 or len(label) > 63:
                raise ValueError(
                    "each label in domain must be between 1 and 63 characters"
                )
            if not all(char.isalnum() or char == "-" for char in label):
                raise ValueError("labels in domain must be alphanumeric or hyphens")
            if label[0] == "-" or label[-1] == "-":
                raise ValueError("labels in domain cannot start or end with a hyphen")


# Answer File Sections
# ---------------------------------------------------------------------------------------


class Global(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    keyboard: str | Placeholder = "en-us"
    country: str | Placeholder = "US"
    fqdn: str | FQDNFromDHCP | Placeholder | None = None
    mailto: str | Placeholder | None = None
    timezone: str | Placeholder | None = None

    root_password: str | Placeholder | None = Field(default=None, alias="root-password")
    root_password_hashed: str | Placeholder | None = Field(
        default=None, alias="root-password-hashed"
    )
    root_ssh_keys: list[str] | Placeholder | None = Field(
        default=None, alias="root-ssh-keys"
    )

    reboot_on_error: bool | Placeholder | None = Field(
        default=None, alias="reboot-on-error"
    )
    reboot_mode: str | Placeholder | None = Field(default=None, alias="reboot-mode")

    @field_validator("keyboard")
    @classmethod
    def _keyboard_allowed(cls, keyboard_selection: str) -> str:
        if keyboard_selection not in ALLOWED_KEYBOARDS and not _is_placeholder(
            keyboard_selection
        ):
            raise ValueError(f"keyboard must be one of {sorted(ALLOWED_KEYBOARDS)}")
        return keyboard_selection

    @field_validator("country")
    @classmethod
    def _country_valid(cls, country_code: str) -> str:
        if len(country_code) != 2 and not _is_placeholder(country_code):
            raise ValueError("country must be a 2-letter ISO 3166-1 alpha-2 code")
        if not country_code.isalpha() and not _is_placeholder(country_code):
            raise ValueError("country must only contain alphabetic characters")
        return country_code.upper()

    @field_validator("mailto")
    @classmethod
    def _mailto_valid(cls, address: str | None) -> str | None:
        if address is not None and not _is_placeholder(address):
            email_regex = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
            if not match(email_regex, address):
                raise ValueError("mailto must be a valid email address")
        return address

    # validate timezone if present
    @field_validator("timezone")
    @classmethod
    def _timezone_valid(cls, zone: str | None) -> str | None:
        if zone is not None and not _is_placeholder(zone):
            # Basic validation for timezone format (e.g., "Region/City")
            if not match(r"^[A-Za-z_]+\/[A-Za-z_]+(?:\/[A-Za-z_]+)?$", zone):
                raise ValueError("timezone must be in the format 'Region/City'")
        return zone

    # validate plaintext password if present
    @field_validator("root_password")
    @classmethod
    def _password_valid(cls, pwd: str | None) -> str | None:
        if pwd is not None and not _is_placeholder(pwd):
            if len(pwd) < 8:
                raise ValueError("root-password must be at least 8 characters")
            if len(pwd) > 64:
                raise ValueError("root-password must be at most 64 characters")
            if search(r"\s", pwd):
                raise ValueError("root-password cannot contain whitespace characters")
            if password_entropy(pwd) < 80.0:
                raise ValueError(
                    "root-password must have an entropy of at least 80 bits"
                )
        return pwd

    # validate hashed password if present
    @field_validator("root_password_hashed")
    @classmethod
    def _hashed_password_valid(cls, pwd: str | None) -> str | None:
        if pwd is not None and not _is_placeholder(pwd):
            # Basic validation for SHA-512 hashed password (starts with $6$)
            if not pwd.startswith("$6$"):
                raise ValueError(
                    "root-password-hashed must be a SHA-512 hash starting with '$6$'"
                )
            # grab the actual hash part and validate
            hash_part = pwd.split("$")[-1]
            if not validate_sha512(hash_part):
                raise ValueError(
                    "root-password-hashed must contain a valid SHA-512 hash"
                )
        return pwd

    # validate ssh keys if present
    @field_validator("root_ssh_keys", mode="before")
    @classmethod
    def _ssh_keys_list(cls, ssh_keys: str | list[str] | None) -> list[str] | None:
        if ssh_keys is None:
            return None
        if isinstance(ssh_keys, str):
            ssh_keys = [ssh_keys]
        for key in ssh_keys:
            if not (
                key.startswith("ssh-rsa ")
                or key.startswith("ssh-ed25519 ")
                or _is_placeholder(key)
            ):
                raise ValueError(
                    "each root-ssh-key must start with 'ssh-rsa ' or 'ssh-ed25519 '"
                )
        return ssh_keys

    @field_validator("reboot_mode")
    @classmethod
    def _reboot_mode_allowed(cls, mode: str | None) -> str | None:
        if (
            mode is not None
            and mode not in ALLOWED_REBOOT_MODES
            and not _is_placeholder(mode)
        ):
            raise ValueError(
                f"reboot-mode must be one of {sorted(ALLOWED_REBOOT_MODES)}"
            )
        return mode

    @model_validator(mode="after")
    def _check_password_xor(self) -> "Global":
        # If either is a placeholder, skip XOR check
        if (
            isinstance(self.root_password, str) and _is_placeholder(self.root_password)
        ) or (
            isinstance(self.root_password_hashed, str)
            and _is_placeholder(self.root_password_hashed)
        ):
            return self
        has_plain = self.root_password is not None
        has_hash = self.root_password_hashed is not None
        if has_plain == has_hash:
            raise ValueError(
                "Exactly one of 'root-password' or 'root-password-hashed' must be set."
            )
        return self


class Network(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source: str | Placeholder
    cidr: IPvAnyInterface | Placeholder | None = None
    dns: IPvAnyAddress | Placeholder | None = None
    gateway: IPvAnyAddress | Placeholder | None = None
    filter: Mapping[str, str] | Placeholder | None = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, source_value: str) -> str:
        if _is_placeholder(source_value):
            return source_value
        if source_value not in ALLOWED_NETWORK_SOURCES:
            raise ValueError(
                f"network.source must be one of {sorted(ALLOWED_NETWORK_SOURCES)}"
            )
        return source_value

    @model_validator(mode="after")
    def validate_network_fields(self) -> "Network":
        # If source or any required/forbidden field is a placeholder, skip logic
        if _is_placeholder(self.source) or any(
            _is_placeholder(val)
            for val in [self.cidr, self.dns, self.gateway, self.filter]  # type: ignore
            if isinstance(val, str)
        ):
            return self
        if self.source == "from-dhcp":
            forbidden_fields: dict[str, object] = {
                "cidr": self.cidr,
                "dns": self.dns,
                "gateway": self.gateway,
                "filter": self.filter,
            }
            set_fields = [
                field for field, value in forbidden_fields.items() if value is not None
            ]
            if set_fields:
                raise ValueError(
                    f"With source=from-dhcp, do not set: {', '.join(set_fields)}."
                )
        elif self.source == "from-answer":
            required_fields: dict[str, object] = {
                "cidr": self.cidr,
                "dns": self.dns,
                "gateway": self.gateway,
            }
            missing_fields = [
                field for field, value in required_fields.items() if value is None
            ]
            if missing_fields:
                raise ValueError(
                    f"With source=from-answer, required: {', '.join(missing_fields)}."
                )
        else:
            raise ValueError(f"Unknown network source: {self.source}")
        return self


class ZfsOpts(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    raid: str | Placeholder = Field(alias="raid")
    ashift: int | Placeholder | None = None
    arc_max: int | Placeholder | None = Field(default=None, alias="arc-max")
    checksum: str | Placeholder | None = "on"
    compress: str | Placeholder | None = "on"
    copies: int | Placeholder | None = None
    hdsize: int | Placeholder | None = None

    @field_validator("raid")
    @classmethod
    def _raid_allowed(cls, raid_value: str) -> str:
        if raid_value not in ALLOWED_ZFS_RAID and not _is_placeholder(raid_value):
            raise ValueError(f"zfs.raid must be one of {sorted(ALLOWED_ZFS_RAID)}")
        return raid_value

    @field_validator("ashift")
    @classmethod
    def _ashift_valid(
        cls, ashift_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        if (
            ashift_value is not None
            and ashift_value is int
            and not (9 <= ashift_value <= 16)
        ):
            raise ValueError("zfs.ashift must be between 9 and 16")
        return ashift_value

    @field_validator("arc_max")
    @classmethod
    def _arc_max_valid(
        cls, arc_max_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        return _verify_positive_integer(arc_max_value, "zfs.arc-max")

    @field_validator("checksum")
    @classmethod
    def _checksum_allowed(
        cls, checksum_value: str | Placeholder | None
    ) -> str | Placeholder | None:
        if (
            checksum_value is not None
            and not _is_placeholder(checksum_value)
            and checksum_value not in ALLOWED_ZFS_CHECKSUM
        ):
            raise ValueError(
                f"zfs.checksum must be one of {sorted(ALLOWED_ZFS_CHECKSUM)}"
            )
        return checksum_value

    @field_validator("compress")
    @classmethod
    def _compress_allowed(
        cls, compress_value: str | Placeholder | None
    ) -> str | Placeholder | None:
        if (
            compress_value is not None
            and not _is_placeholder(compress_value)
            and compress_value not in ALLOWED_ZFS_COMPRESS
        ):
            raise ValueError(
                f"zfs.compress must be one of {sorted(ALLOWED_ZFS_COMPRESS)}"
            )
        return compress_value

    @field_validator("copies")
    @classmethod
    def _copies_valid(
        cls, copies_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        if (
            copies_value is not None
            and copies_value is int
            and copies_value not in (1, 2, 3)
        ):
            raise ValueError("zfs.copies must be 1, 2, or 3")
        return copies_value

    @field_validator("hdsize")
    @classmethod
    def _hdsize_valid(
        cls, hdsize_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        return _verify_positive_integer(hdsize_value, "zfs.hdsize")


class LvmOpts(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    hdsize: int | Placeholder | None = None
    swapsize: int | Placeholder | None = None
    maxroot: int | Placeholder | None = None
    maxvz: int | Placeholder | None = None
    minfree: int | Placeholder | None = None

    @field_validator("hdsize")
    @classmethod
    def _hdsize_valid(
        cls, hdsize_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        return _verify_positive_integer(hdsize_value, "lvm.hdsize")

    @field_validator("swapsize")
    @classmethod
    def _swapsize_valid(
        cls, swapsize_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        return _verify_positive_integer(swapsize_value, "lvm.swapsize")

    @field_validator("maxroot")
    @classmethod
    def _maxroot_valid(
        cls, maxroot_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        return _verify_positive_integer(maxroot_value, "lvm.maxroot")

    @field_validator("maxvz")
    @classmethod
    def _maxvz_valid(
        cls, maxvz_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        return _verify_positive_integer(maxvz_value, "lvm.maxvz")

    @field_validator("minfree")
    @classmethod
    def _minfree_valid(
        cls, minfree_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        return _verify_positive_integer(minfree_value, "lvm.minfree")


class BtrfsOpts(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    raid: str | Placeholder
    hdsize: int | Placeholder | None = None
    compress: str | Placeholder | None = "off"

    @field_validator("raid")
    @classmethod
    def _raid_allowed(cls, raid_value: str) -> str:
        if not _is_placeholder(raid_value) and raid_value not in ALLOWED_BTRFS_RAID:
            raise ValueError(f"btrfs.raid must be one of {sorted(ALLOWED_BTRFS_RAID)}")
        return raid_value

    @field_validator("hdsize")
    @classmethod
    def _hdsize_valid(
        cls, hdsize_value: int | Placeholder | None
    ) -> int | Placeholder | None:
        return _verify_positive_integer(hdsize_value, "btrfs.hdsize")

    @field_validator("compress")
    @classmethod
    def _compress_allowed(cls, compress_value: str | None) -> str | None:
        if (
            compress_value is not None
            and not _is_placeholder(compress_value)
            and compress_value not in ALLOWED_BTRFS_COMPRESS
        ):
            raise ValueError(
                f"btrfs.compress must be one of {sorted(ALLOWED_BTRFS_COMPRESS)}"
            )
        return compress_value


class DiskSetup(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    filesystem: str | Placeholder
    disk_list: list[str] | Placeholder | None = Field(default=None, alias="disk-list")
    filter: Mapping[str, str] | Placeholder | None = None
    filter_match: str | Placeholder | None = Field(default="any", alias="filter-match")

    zfs: ZfsOpts | Placeholder | None = None
    lvm: LvmOpts | Placeholder | None = None
    btrfs: BtrfsOpts | Placeholder | None = None

    @field_validator("filesystem")
    @classmethod
    def _filesystem_allowed(cls, filesystem_value: str) -> str:
        if (
            not _is_placeholder(filesystem_value)
            and filesystem_value not in ALLOWED_FILESYSTEMS
        ):
            raise ValueError(f"filesystem must be one of {sorted(ALLOWED_FILESYSTEMS)}")
        return filesystem_value

    @field_validator("filter_match")
    @classmethod
    def _filter_match_allowed(cls, filter_match_value: str | None) -> str | None:
        if (
            filter_match_value is not None
            and not _is_placeholder(filter_match_value)
            and filter_match_value not in ALLOWED_FILTER_MATCH
        ):
            raise ValueError(
                f"filter-match must be one of {sorted(ALLOWED_FILTER_MATCH)}"
            )
        return filter_match_value

    @field_validator("disk_list")
    @classmethod
    def _disk_list_valid(cls, disk_list_value: list[str] | None) -> list[str] | None:
        if disk_list_value is not None:
            if not disk_list_value:
                raise ValueError("disk-list cannot be empty")
            for disk in disk_list_value:
                if not disk:
                    raise ValueError(
                        "Each disk in disk-list must be a non-empty string"
                    )
        return disk_list_value

    @field_validator("filter")
    @classmethod
    def _filter_valid(
        cls, filter_value: Mapping[str, str] | str | None
    ) -> Mapping[str, str] | str | None:
        if (
            filter_value is not None
            and not (isinstance(filter_value, str) and _is_placeholder(filter_value))
            and isinstance(filter_value, Mapping)
        ):
            for key, _ in filter_value.items():
                if not key:
                    raise ValueError("Each filter key must be a non-empty string")
        return filter_value

    @model_validator(mode="after")
    def _validate_disks_and_filesystem(self) -> "DiskSetup":
        self._validate_disk_list_and_filter()
        self._validate_filesystem_sections()
        return self

    def _validate_disk_list_and_filter(self) -> None:
        # If either disk_list or filter is a placeholder, skip logic
        is_disk_list_placeholder = isinstance(self.disk_list, str) and _is_placeholder(
            self.disk_list
        )
        is_filter_placeholder = isinstance(self.filter, str) and _is_placeholder(
            self.filter
        )
        if is_disk_list_placeholder or is_filter_placeholder:
            return
        if self.disk_list is not None and self.filter is not None:
            raise ValueError("Use either 'disk-list' or 'filter', not both.")
        if self.disk_list is None and self.filter is None:
            raise ValueError("One of 'disk-list' or 'filter' must be set.")

    def _validate_filesystem_sections(self) -> None:
        if _is_placeholder(self.filesystem):
            # If filesystem is a placeholder, skip sub-section validation
            return
        if self.filesystem == "zfs":
            self._validate_zfs_section()
        elif self.filesystem == "btrfs":
            self._validate_btrfs_section()
        elif self.filesystem == "lvm":
            self._validate_lvm_section()
        else:
            self._validate_ext4_xfs_section()

    def _validate_zfs_section(self) -> None:
        if self.zfs is None:
            raise ValueError(
                "For filesystem=zfs, section [disk-setup.zfs] is required."
            )
        if self.lvm is not None or self.btrfs is not None:
            raise ValueError("For filesystem=zfs, only [disk-setup.zfs] must be set.")

    def _validate_btrfs_section(self) -> None:
        if self.btrfs is None:
            raise ValueError(
                "For filesystem=btrfs, section [disk-setup.btrfs] is required."
            )
        if self.lvm is not None or self.zfs is not None:
            raise ValueError(
                "For filesystem=btrfs, only [disk-setup.btrfs] can be set."
            )

    def _validate_lvm_section(self) -> None:
        if self.lvm is None:
            raise ValueError(
                "For filesystem=lvm, section [disk-setup.lvm] is required."
            )
        if self.zfs is not None or self.btrfs is not None:
            raise ValueError("For filesystem=lvm, only [disk-setup.lvm] must be set.")

    def _validate_ext4_xfs_section(self) -> None:
        if self.zfs is not None or self.lvm is not None or self.btrfs is not None:
            raise ValueError(
                f"For filesystem={self.filesystem}, do not set zfs, lvm, or btrfs options."
            )


class PostInstallationWebhook(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    url: HttpUrl | Placeholder
    cert_fingerprint: str | Placeholder | None = Field(
        default=None, alias="cert-fingerprint"
    )

    @field_validator("cert_fingerprint")
    @classmethod
    def _cert_fingerprint_valid(cls, cert_fingerprint_value: str | None) -> str | None:
        if cert_fingerprint_value is not None and not _is_placeholder(
            cert_fingerprint_value
        ):
            # Accept SHA-256 or SHA-1 hex fingerprint (colon or no colon)
            fingerprint_regex = (
                r"^([A-Fa-f0-9]{2}:){31}[A-Fa-f0-9]{2}$"  # SHA-256 with colons
                r"|^([A-Fa-f0-9]{64})$"  # SHA-256 no colons
                r"|^([A-Fa-f0-9]{2}:){19}[A-Fa-f0-9]{2}$"  # SHA-1 with colons
                r"|^([A-Fa-f0-9]{40})$"  # SHA-1 no colons
            )
            if not match(fingerprint_regex, cert_fingerprint_value):
                raise ValueError(
                    "cert-fingerprint must be a valid SHA-256 or SHA-1 hex fingerprint"
                )
        return cert_fingerprint_value


class FirstBoot(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    source: str | Placeholder
    ordering: str | Placeholder | None = "fully-up"
    url: HttpUrl | Placeholder | None = None
    cert_fingerprint: str | Placeholder | None = Field(
        default=None, alias="cert-fingerprint"
    )

    @field_validator("source")
    @classmethod
    def _source_allowed(cls, v: str) -> str:
        if v not in ALLOWED_FIRST_BOOT_SOURCES and not _is_placeholder(v):
            raise ValueError(
                f"first-boot.source must be one of {sorted(ALLOWED_FIRST_BOOT_SOURCES)}"
            )
        return v

    @field_validator("ordering")
    @classmethod
    def _ordering_allowed(cls, v: str | None) -> str | None:
        if (
            v is not None
            and not _is_placeholder(v)
            and v not in ALLOWED_FIRST_BOOT_ORDERING
        ):
            raise ValueError(
                f"first-boot.ordering must be one of {sorted(ALLOWED_FIRST_BOOT_ORDERING)}"
            )
        return v

    @field_validator("cert_fingerprint")
    @classmethod
    def _cert_fingerprint_valid(cls, cert_fingerprint_value: str | None) -> str | None:
        if cert_fingerprint_value is not None and not _is_placeholder(
            cert_fingerprint_value
        ):
            # Accept SHA-256 or SHA-1 hex fingerprint (colon or no colon)
            fingerprint_regex = (
                r"^([A-Fa-f0-9]{2}:){31}[A-Fa-f0-9]{2}$"  # SHA-256 with colons
                r"|^([A-Fa-f0-9]{64})$"  # SHA-256 no colons
                r"|^([A-Fa-f0-9]{2}:){19}[A-Fa-f0-9]{2}$"  # SHA-1 with colons
                r"|^([A-Fa-f0-9]{40})$"  # SHA-1 no colons
            )
            if not match(fingerprint_regex, cert_fingerprint_value):
                raise ValueError(
                    "cert-fingerprint must be a valid SHA-256 or SHA-1 hex fingerprint"
                )
        return cert_fingerprint_value

    @model_validator(mode="after")
    def _validate_source_url(self) -> "FirstBoot":
        # If source or url is a placeholder, skip logic
        if _is_placeholder(self.source) or (
            _is_placeholder(self.url) if isinstance(self.url, str) else False
        ):
            return self
        if self.source == "from-url" and self.url is None:
            raise ValueError("With first-boot.source=from-url, 'url' is required.")
        if self.source == "from-iso" and self.url is not None:
            raise ValueError("With first-boot.source=from-iso, do not set 'url'.")
        return self


# Top-level Answer File
class AnswerFile(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    global_: Global | Placeholder = Field(alias="global")
    network: Network | Placeholder
    disk_setup: DiskSetup | Placeholder = Field(alias="disk-setup")
    post_installation_webhook: PostInstallationWebhook | None = Field(
        default=None, alias="post-installation-webhook"
    )
    first_boot: FirstBoot | Placeholder | None = Field(default=None, alias="first-boot")


# Utility functions
# ---------------------------------------------------------------------------------------


# Loader
def load_answer_file(path: Path) -> AnswerFile:
    """Load and parse the AnswerFile from a TOML file.
    Args:
        path (Path): The path to the TOML file.

    Returns:
        AnswerFile: The parsed AnswerFile model.

    Raises:
        FileNotFoundError: If the file does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
        pydantic.ValidationError: If the data does not conform to the AnswerFile model.
    """
    with path.open("rb") as f:
        data = toml_load(f)
    return AnswerFile.model_validate(data)


# Dumper
def dump_answer_file(answer_file: AnswerFile, path: Path) -> None:
    """Serialize the AnswerFile model back to TOML and write it to a file.

    Args:
        answer_file (AnswerFile): The AnswerFile model to serialize.
        path (Path): The path to the output TOML file.

    Raises:
        IOError: If there is an error writing to the file.
    """
    # Convert to dict, respecting aliases like "root-password"
    data = answer_file.model_dump(by_alias=True, exclude_none=True)

    # Convert any Non-serializable types to strings
    for section in [
        "network",
        "disk-setup",
        "global",
        "first-boot",
        "disk-setup.zfs",
        "disk-setup.lvm",
        "disk-setup.btrfs",
        "post-installation-webhook",
    ]:
        if section in data:
            for key, value in data[section].items():
                if isinstance(
                    value,
                    (IPv4Interface, IPv6Interface, IPv4Address, IPv6Address, HttpUrl),
                ):
                    data[section][key] = str(value)

    # Turn dict into TOML string
    toml_str = dumps(data)

    # Write string to file
    path.write_text(toml_str, encoding="utf-8")
