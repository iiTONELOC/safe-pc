from re import compile as re_compile
from pydantic import BaseModel, Field, field_validator
from safe_pc.proxmox_auto_installer.constants import (
    PROXMOX_ALLOWED_FILESYSTEMS,
    PROXMOX_ALLOWED_ZFS_RAID,
    PROXMOX_ALLOWED_BTRFS_RAID,
)

DISK_PATH_PATTERN = re_compile(r"^/dev/[a-zA-Z0-9]+$")
FILESYSTEM_PATTERN = re_compile(r"^(ext4|xfs|zfs|btrfs)$")
BTRFS_RAID_PATTERN = re_compile(r"^(raid0|raid1|raid10)$")
ZFS_RAID_PATTERN = re_compile(r"^(raid0|raid1|raid10|raidz-1|raidz-2|raidz-3)$")

DISK_CONFIG_DEFAULTS = {
    "filesystem": "zfs",
    "zfs_raid": "raid0",
    "btrfs_raid": None,
    "disk_list": ["/dev/sda"],
}


class DiskConfig(BaseModel):
    model_config = {"populate_by_name": True}

    filesystem: str = Field(
        default=DISK_CONFIG_DEFAULTS["filesystem"],
        description="Filesystem type for disk setup",
        pattern=FILESYSTEM_PATTERN.pattern,
    )

    btrfs_raid: str | None = Field(
        default=DISK_CONFIG_DEFAULTS["btrfs_raid"],
        description="Btrfs RAID configuration (required if filesystem is btrfs)",
        alias="btrfs.raid",
        pattern=BTRFS_RAID_PATTERN.pattern,
    )

    zfs_raid: str | None = Field(
        default=DISK_CONFIG_DEFAULTS["zfs_raid"],
        description="ZFS RAID configuration (required if filesystem is zfs)",
        alias="zfs.raid",
        pattern=ZFS_RAID_PATTERN.pattern,
    )

    disk_list: list[str] = Field(
        default=DISK_CONFIG_DEFAULTS["disk_list"],
        description="List of disks to use for installation",
        min_length=1,
        max_length=10,
        alias="disk-list",
    )

    @field_validator("filesystem", mode="before")
    def validate_filesystem_pattern(cls, value: str):
        if not FILESYSTEM_PATTERN.match(value):
            raise ValueError(f"Invalid filesystem pattern: {value}")
        return value

    @field_validator("filesystem")
    def validate_filesystem_allowed(cls, value: str):
        if value not in PROXMOX_ALLOWED_FILESYSTEMS:
            raise ValueError(f"Invalid filesystem: {value}")
        return value

    @field_validator("zfs_raid", mode="before")
    def validate_zfs_raid_required(cls, raid_value, values):
        fs = values.data.get("filesystem")
        if fs == "zfs":
            if raid_value is None:
                raise ValueError(
                    "ZFS RAID configuration is required when filesystem is zfs"
                )
            if raid_value not in PROXMOX_ALLOWED_ZFS_RAID:
                raise ValueError(f"Invalid ZFS RAID configuration: {raid_value}")
        return raid_value

    @field_validator("zfs_raid")
    def validate_zfs_raid_pattern(cls, value: str | None):
        if value and not ZFS_RAID_PATTERN.match(value):
            raise ValueError(f"Invalid zfs_raid pattern: {value}")
        return value

    @field_validator("btrfs_raid", mode="before")
    def validate_btrfs_raid_required(cls, raid_value, values):
        fs = values.data.get("filesystem")
        if fs == "btrfs":
            if raid_value is None:
                raise ValueError(
                    "Btrfs RAID configuration is required when filesystem is btrfs"
                )
            if raid_value not in PROXMOX_ALLOWED_BTRFS_RAID:
                raise ValueError(f"Invalid Btrfs RAID configuration: {raid_value}")
        return raid_value

    @field_validator("btrfs_raid")
    def validate_btrfs_raid_pattern(cls, value: str | None):
        if value and not BTRFS_RAID_PATTERN.match(value):
            raise ValueError(f"Invalid btrfs_raid pattern: {value}")
        return value

    @field_validator("disk_list", mode="before")
    def validate_disk_list_nonempty(cls, disk_list_value: list[str]):
        if not disk_list_value:
            raise ValueError("disk-list must be a non-empty list of disk identifiers")
        return disk_list_value

    @field_validator("disk_list")
    def validate_disk_list_paths(cls, disk_list_value: list[str], values):
        for disk in disk_list_value:
            if not DISK_PATH_PATTERN.match(disk):
                raise ValueError(f"Invalid disk path: {disk}")

        fs = values.data.get("filesystem")
        raid = None
        if fs == "zfs":
            raid = values.data.get("zfs_raid")
        elif fs == "btrfs":
            raid = values.data.get("btrfs_raid")

        raid_disk_requirements = {
            "zfs": {
                "raid0": 1,
                "raid1": 2,
                "raid10": 2,
                "raidz-1": 3,
                "raidz-2": 4,
                "raidz-3": 5,
            },
            "btrfs": {
                "raid1": 2,
                "raid10": 2,
            },
        }

        if fs in raid_disk_requirements and raid in raid_disk_requirements[fs]:
            required_disks = raid_disk_requirements[fs][raid]
            if len(disk_list_value) < required_disks:
                fs_label = "ZFS" if fs == "zfs" else "Btrfs"
                raise ValueError(
                    f"At least {required_disks} disks are required for {fs_label} {raid}"
                )
        return disk_list_value
