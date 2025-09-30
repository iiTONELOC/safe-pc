from safe_pc.proxmox_auto_installer.constants import (
    PROXMOX_ALLOWED_FILESYSTEMS,
    PROXMOX_ALLOWED_ZFS_RAID,
    PROXMOX_ALLOWED_BTRFS_RAID,
)
from safe_pc.proxmox_auto_installer.utils.tzd import ProxmoxTimezoneHelper
from pydantic import BaseModel, Field, field_validator

# note: Not really sure we will let users select anything here


"""
        "disk-setup": {
            "filesystem": "zfs",
            "zfs.raid": "raid0",
            "disk-list": [f"{disk}"],
        },
"""


class DiskConfig(BaseModel):
    filesystem: str = Field(
        default="zfs",
        Required=True,
        description="Filesystem type for disk setup",
        example="zfs",
        regex="^(ext4|xfs|zfs|btrfs)$",
    )

    zfs_raid: str | None = Field(
        default="raid0",
        description="ZFS RAID configuration (required if filesystem is zfs)",
        example="raid0",
        regex="^(raid0|raid1|raid10|raidz-1|raidz-2|raidz-3)$",
        alias="zfs.raid",
    )

    btrfs_raid: str | None = Field(
        default=None,
        description="Btrfs RAID configuration (required if filesystem is btrfs)",
        example="raid1",
        regex="^(raid0|raid1|raid10)$",
        alias="btrfs.raid",
    )

    disk_list: list[str] = Field(
        default_factory=list,
        Required=True,
        description="List of disks to use for installation",
        example=["/dev/sda"],
        min_items=1,
        max_items=10,
        regex=r"^/dev/[a-zA-Z0-9]+$",
    )

    # validate each field, for example if raid 1 is selected, ensure at least 2 disks are provided
    # and so on.

    @field_validator("filesystem")
    def validate_filesystem(cls, fs_value):
        if fs_value not in PROXMOX_ALLOWED_FILESYSTEMS:
            raise ValueError(f"Invalid filesystem: {fs_value}")
        return fs_value

    @field_validator("zfs_raid", mode="before")
    def validate_zfs_raid(cls, raid_value, values):
        if values.get("filesystem") == "zfs":
            if raid_value is None:
                raise ValueError(
                    "ZFS RAID configuration is required when filesystem is zfs"
                )
            if raid_value not in PROXMOX_ALLOWED_ZFS_RAID:
                raise ValueError(f"Invalid ZFS RAID configuration: {raid_value}")
        return raid_value

    @field_validator("btrfs_raid", mode="before")
    def validate_btrfs_raid(cls, raid_value, values):
        if values.get("filesystem") == "btrfs":
            if raid_value is None:
                raise ValueError(
                    "Btrfs RAID configuration is required when filesystem is btrfs"
                )
            if raid_value not in PROXMOX_ALLOWED_BTRFS_RAID:
                raise ValueError(f"Invalid Btrfs RAID configuration: {raid_value}")
        return raid_value

    @field_validator("disk_list")
    def validate_disk_list(cls, disk_list_value):
        if len(disk_list_value) == 0:
            raise ValueError("disk-list must be a non-empty list of disk identifiers")
        for disk in disk_list_value:
            if not isinstance(disk, str) or not disk.startswith("/dev/"):
                raise ValueError(f"Invalid disk identifier: {disk}")
        return disk_list_value

    @field_validator("disk_list")
    def validate_disk_count_for_raid(cls, disk_list_value, values):
        fs = values.get("filesystem")
        raid = (
            values.get("zfs_raid")
            if fs == "zfs"
            else values.get("btrfs_raid") if fs == "btrfs" else None
        )

        raid_disk_requirements = {
            "zfs": {
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
