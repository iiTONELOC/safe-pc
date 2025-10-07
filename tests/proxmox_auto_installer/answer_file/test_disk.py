import pytest
from pydantic import ValidationError
from safe_pc.proxmox_auto_installer.answer_file.disk import DiskConfig


def test_disk_defaults():
    cfg = DiskConfig()
    assert cfg.filesystem == "zfs"
    assert cfg.zfs_raid == "raid0"
    assert cfg.btrfs_raid is None
    assert cfg.disk_list == ["/dev/sda"]


# Filesystem Tests
def test_filesystem_xfs_ext4_btrfs_valid():
    for fs in ["ext4", "xfs", "btrfs"]:
        cfg = DiskConfig(filesystem=fs, disk_list=["/dev/sda"])
        assert cfg.filesystem == fs


def test_filesystem_invalid_pattern():
    # Pattern-level regex validation
    with pytest.raises(ValidationError):
        DiskConfig(filesystem="1234")


# ZFS RAID Tests
@pytest.mark.parametrize(
    "raid,disk_count",
    [
        ("raid0", 2),
        ("raid1", 2),
        ("raid10", 2),
        ("raidz-1", 3),
        ("raidz-2", 4),
        ("raidz-3", 5),
    ],
)
def test_zfs_raid_valid_patterns(raid, disk_count):
    disks = [f"/dev/sd{i}" for i in range(disk_count)]
    cfg = DiskConfig(
        filesystem="zfs",
        zfs_raid=raid,
        disk_list=disks,
    )
    assert cfg.zfs_raid == raid


def test_zfs_raid_required_when_zfs():
    with pytest.raises(ValidationError):
        DiskConfig(filesystem="zfs", zfs_raid=None, disk_list=["/dev/sda"])


def test_zfs_raid_disk_count_enforcement():
    # raidz-1 requires 3 disks
    with pytest.raises(ValidationError):
        DiskConfig(
            filesystem="zfs", zfs_raid="raidz-1", disk_list=["/dev/sda", "/dev/sdb"]
        )
    # raidz-2 requires 4 disks
    with pytest.raises(ValidationError):
        DiskConfig(filesystem="zfs", zfs_raid="raidz-2", disk_list=["/dev/sda"] * 3)
    # raidz-3 requires 5 disks
    with pytest.raises(ValidationError):
        DiskConfig(filesystem="zfs", zfs_raid="raidz-3", disk_list=["/dev/sda"] * 4)


# Btrfs RAID Tests
@pytest.mark.parametrize(
    "raid,disk_count",
    [
        ("raid0", 1),
        ("raid0", 2),
        ("raid1", 2),
        ("raid10", 2),
    ],
)
def test_btrfs_raid_valid_patterns(raid, disk_count):
    disks = [f"/dev/sd{i}" for i in range(disk_count)]
    cfg = DiskConfig(filesystem="btrfs", btrfs_raid=raid, disk_list=disks)
    assert cfg.btrfs_raid == raid


def test_btrfs_raid_required_when_btrfs():
    with pytest.raises(ValidationError):
        DiskConfig(filesystem="btrfs", btrfs_raid=None, disk_list=["/dev/sda"])


def test_btrfs_raid_disk_count_enforcement():
    # raid1 requires 2 disks
    with pytest.raises(ValidationError):
        DiskConfig(filesystem="btrfs", btrfs_raid="raid1", disk_list=["/dev/sda"])
    # raid10 requires 2 disks
    with pytest.raises(ValidationError):
        DiskConfig(filesystem="btrfs", btrfs_raid="raid10", disk_list=["/dev/sda"])


# Disk List Edge Cases
def test_disk_list_invalid_path_format():
    invalid_paths = ["dev/sda", "/sdX", "///dev/sda", "/dev/", "/dev//sda"]
    for path in invalid_paths:
        with pytest.raises(ValidationError):
            DiskConfig(disk_list=[path])


def test_disk_list_non_string_items():
    with pytest.raises(ValidationError):
        DiskConfig(disk_list=[123])
    with pytest.raises(ValidationError):
        DiskConfig(disk_list=[None])


# Alias & Name Population Tests
def test_alias_population_for_zfs_raid():
    cfg = DiskConfig(
        filesystem="zfs", zfs_raid="raid1", disk_list=["/dev/sda", "/dev/sdb"]
    )
    dumped = cfg.model_dump(by_alias=True)
    assert "zfs.raid" in dumped
    assert dumped["zfs.raid"] == "raid1"


def test_alias_population_for_btrfs_raid():
    cfg = DiskConfig(
        filesystem="btrfs", btrfs_raid="raid1", disk_list=["/dev/sda", "/dev/sdb"]
    )
    dumped = cfg.model_dump(by_alias=True)
    assert "btrfs.raid" in dumped
    assert dumped["btrfs.raid"] == "raid1"


# Mixed Scenario Tests
def test_zfs_raid_ignored_when_btrfs():
    # Should accept zfs_raid=None when btrfs
    cfg = DiskConfig(
        filesystem="btrfs",
        btrfs_raid="raid1",
        zfs_raid=None,
        disk_list=["/dev/sda", "/dev/sdb"],
    )
    assert cfg.btrfs_raid == "raid1"


def test_btrfs_raid_ignored_when_zfs():
    cfg = DiskConfig(
        filesystem="zfs",
        zfs_raid="raid0",
        btrfs_raid=None,
        disk_list=["/dev/sda", "/dev/sdb"],
    )
    assert cfg.zfs_raid == "raid0"
