from safe_pc.proxmox_auto_installer.constants import (
    PROXMOX_ALLOWED_KEYBOARDS,
    PROXMOX_ALLOWED_FILESYSTEMS,
    PROXMOX_ALLOWED_ZFS_RAID,
    PROXMOX_ALLOWED_BTRFS_RAID,
    PROXMOX_ALLOWED_FIRST_BOOT_SOURCES,
    PROXMOX_ALLOWED_FIRST_BOOT_ORDERING,
)
from safe_pc.proxmox_auto_installer.utils.tzd import ProxmoxTimezoneHelper
from pydantic import BaseModel, Field, field_validator


class AnswerFileSection(BaseModel):
    section_name: str
    options: dict[str, str]


"""
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
"""


class GlobalConfig(BaseModel):
    keyboard: str = Field(
        default="us",
        Required=True,
        description="Keyboard layout code",
        example="us",
        regex="^[a-z]{2}(-[a-z]{2})?$",
    )
    country: str = Field(
        default="us",
        Required=True,
        description="Country code",
        example="us",
        regex="^[a-z]{2}(-[a-z]{2})?$",
    )
    timezone: str = Field(
        default="America/New_York",
        Required=True,
        description="Timezone string",
        example="America/New_York",
        regex="^[A-Za-z_]+/[A-Za-z_]+(/[A-Za-z_]+)?$",
    )
    fqdn: str = Field(
        default="proxmox.lab.local",
        Required=True,
        description="Fully Qualified Domain Name for the Proxmox server",
        example="proxmox.lab.local",
        regex="^(?=.{1,255}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\\.)+[a-zA-Z]{2,63}$",
    )
    mailto: str = Field(
        default="root@localhost",
        description="Email address for system notifications",
        example="root@localhost",
        regex="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
    )
    root_password_hashed: str = Field(
        ...,
        description="Hashed root password for the Proxmox server",
        example="$6$rounds=656000$saltsalt$hashedpasswordhashhashhashhashhashhashhashhashhash",
        regex="^\\$6\\$rounds=\\d+\\$[./A-Za-z0-9]{8}\\$[./A-Za-z0-9]{86}$",
    )

    @field_validator("keyboard")
    @classmethod
    def validate_keyboard(cls, v: str) -> str:
        if v not in PROXMOX_ALLOWED_KEYBOARDS:
            raise ValueError(f"Invalid keyboard layout: {v}")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        tz_helper = ProxmoxTimezoneHelper()
        if v not in tz_helper.get_timezones():
            raise ValueError(f"Invalid timezone: {v}")
        return v
