# Allowed values
PROXMOX_ALLOWED_KEYBOARDS = {
    "de",
    "de-ch",
    "dk",
    "en-gb",
    "en-us",
    "es",
    "fi",
    "fr",
    "fr-be",
    "fr-ca",
    "fr-ch",
    "hu",
    "is",
    "it",
    "jp",
    "lt",
    "mk",
    "nl",
    "no",
    "pl",
    "pt",
    "pt-br",
    "se",
    "si",
    "tr",
}
PROXMOX_ALLOWED_REBOOT_MODES = {"reboot", "power-off"}
PROXMOX_ALLOWED_NETWORK_SOURCES = {"from-dhcp", "from-answer"}
PROXMOX_ALLOWED_FILESYSTEMS = {"ext4", "xfs", "zfs", "btrfs"}
PROXMOX_ALLOWED_FILTER_MATCH = {"any", "all"}

PROXMOX_ALLOWED_ZFS_RAID = {
    "raid0",
    "raid1",
    "raid10",
    "raidz-1",
    "raidz-2",
    "raidz-3",
}
PROXMOX_ALLOWED_ZFS_CHECKSUM = {"on", "fletcher4", "sha256"}
PROXMOX_ALLOWED_ZFS_COMPRESS = {
    "on",
    "off",
    "lzjb",
    "lz4",
    "zle",
    "gzip",
    "zstd",
}

PROXMOX_ALLOWED_BTRFS_RAID = {"raid0", "raid1", "raid10"}
PROXMOX_ALLOWED_BTRFS_COMPRESS = {"on", "off", "zlib", "lzo", "zstd"}

PROXMOX_ALLOWED_FIRST_BOOT_SOURCES = {"from-iso", "from-url"}
PROXMOX_ALLOWED_FIRST_BOOT_ORDERING = {
    "before-network",
    "network-online",
    "fully-up",
}
