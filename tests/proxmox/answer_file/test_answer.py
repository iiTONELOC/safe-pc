"""
Author: Anthony Tropeano
CYBV498: Senior Capstone in Cyber Operations
Date: 2025-09-20
Description: This module provides tests for the Proxmox Answer File.
"""

import pytest
from typing import Any
from pathlib import Path
from pydantic import ValidationError


from capstone.proxmox.answer_file.answer import (
    Global,
    Network,
    ZfsOpts,
    LvmOpts,
    FirstBoot,
    DiskSetup,
    BtrfsOpts,
    AnswerFile,
    FQDNFromDHCP,
    PostInstallationWebhook,
    dump_answer_file,
    load_answer_file,
)


def valid_global(**kwargs: Any) -> dict[str, Any]:
    # Provide a valid Global section, allow overrides
    base: dict[str, Any] = {
        "keyboard": "en-us",
        "country": "US",
        "fqdn": "host.example.com",
        "mailto": "admin@example.com",
        "timezone": "America/New_York",
        "root_password": "StrongP@ssw0rd!",
        "root_ssh_keys": ["ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC..."],
        "reboot_on_error": True,
        "reboot_mode": "reboot",
    }
    base.update(kwargs)
    # Remove root_password_hashed if present, to avoid XOR error
    base.pop("root_password_hashed", None)
    return base


def valid_network(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "source": "from-answer",
        "cidr": "192.168.1.10/24",
        "dns": "8.8.8.8",
        "gateway": "192.168.1.1",
    }
    base.update(kwargs)
    return base


def valid_zfs_opts(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "raid": "raid1",
        "ashift": 12,
        "arc_max": 1024,
        "checksum": "on",
        "compress": "lz4",
        "copies": 2,
        "hdsize": 100,
    }
    base.update(kwargs)
    return base


def valid_disk_setup(**kwargs: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "filesystem": "zfs",
        "disk_list": ["/dev/sda", "/dev/sdb"],
        "zfs": valid_zfs_opts(),
    }
    base.update(kwargs)
    return base


def valid_first_boot(**kwargs: Any) -> dict[str, Any]:
    base = {
        "source": "from-iso",
        "ordering": "fully-up",
    }
    base.update(kwargs)
    return base


def valid_post_installation_webhook(**kwargs: Any) -> dict[str, Any]:
    base = {
        "url": "https://webhook.example.com",
        "cert_fingerprint": "A1:" * 31 + "A1",
    }
    base.update(kwargs)
    return base


def valid_answer_file_dict(**overrides: dict[str, Any]):
    base = {
        "global_": valid_global(),
        "network": valid_network(),
        "disk_setup": valid_disk_setup(),
        "post_installation_webhook": valid_post_installation_webhook(),
        "first_boot": valid_first_boot(),
    }
    base.update(overrides)
    # Fix aliases for AnswerFile
    base["global"] = base.pop("global_")
    base["disk-setup"] = base.pop("disk_setup")
    base["post-installation-webhook"] = base.pop("post_installation_webhook")
    base["first-boot"] = base.pop("first_boot")
    return base


def test_global_keyboard_invalid():
    data = valid_global(keyboard="invalid-keyboard")
    data["root_password"] = "StrongP@ssw0rd!"
    with pytest.raises(ValidationError):
        Global(**data)


def test_global_password_xor():
    # Both passwords set
    data = valid_global(root_password="abc123456", root_password_hashed="$6$hash")
    with pytest.raises(ValidationError):
        Global(**data)
    # Neither set
    data = valid_global()
    data.pop("root_password")
    with pytest.raises(ValidationError):
        Global(**data)


def test_network_from_dhcp_forbids_fields():
    data = valid_network(source="from-dhcp", cidr=None, dns=None, gateway=None)
    # Should be valid
    Network(**data)
    # Set forbidden field
    data = valid_network(source="from-dhcp", cidr="192.168.1.10/24")
    with pytest.raises(ValidationError):
        Network(**data)


def test_network_from_answer_requires_fields():
    data = valid_network(source="from-answer", cidr=None)
    with pytest.raises(ValidationError):
        Network(**data)


def test_disk_setup_requires_disk_list_or_filter():
    data = valid_disk_setup()
    data["disk_list"] = None
    data["filter"] = None
    with pytest.raises(ValidationError):
        DiskSetup(**data)


def test_disk_setup_both_disk_list_and_filter():
    data = valid_disk_setup()
    data["filter"] = {"model": "Samsung"}
    with pytest.raises(ValidationError):
        DiskSetup(**data)


def test_disk_setup_zfs_section_required():
    data = valid_disk_setup()
    data["zfs"] = None
    with pytest.raises(ValidationError):
        DiskSetup(**data)


def test_disk_setup_ext4_forbids_zfs_lvm_btrfs():
    data = valid_disk_setup(filesystem="ext4")
    data["zfs"] = valid_zfs_opts()
    with pytest.raises(ValidationError):
        DiskSetup(**data)


def test_post_installation_webhook_cert_fingerprint_invalid():
    data = valid_post_installation_webhook(cert_fingerprint="notavalidfingerprint")
    with pytest.raises(ValidationError):
        PostInstallationWebhook(**data)


def test_first_boot_source_url_logic():
    # from-url requires url
    data = valid_first_boot(source="from-url", url=None)
    with pytest.raises(ValidationError):
        FirstBoot(**data)
    # from-iso forbids url
    data = valid_first_boot(source="from-iso", url="https://example.com")
    with pytest.raises(ValidationError):
        FirstBoot(**data)


def test_answer_file_full_valid():
    data = valid_answer_file_dict()
    af = AnswerFile.model_validate(data)
    assert af.global_.keyboard == "en-us"  # type: ignore
    assert af.disk_setup.filesystem == "zfs"  # type: ignore


def test_dump_and_load_answer_file(tmp_path: Path):
    data = valid_answer_file_dict()
    af = AnswerFile.model_validate(data)
    file_path = tmp_path / "answer.toml"
    dump_answer_file(af, file_path)
    loaded = load_answer_file(file_path)
    assert loaded.global_.keyboard == af.global_.keyboard  # type: ignore
    assert loaded.disk_setup.filesystem == af.disk_setup.filesystem  # type: ignore


def test_fqdn_from_dhcp_valid():
    fqdn = FQDNFromDHCP(source="from-dhcp", domain="example.com")
    assert fqdn.source == "from-dhcp"
    assert fqdn.domain == "example.com"


def test_fqdn_from_dhcp_invalid_source():
    with pytest.raises(ValidationError):
        FQDNFromDHCP(source="static", domain="example.com")


def test_btrfs_opts_invalid_raid():
    with pytest.raises(ValidationError):
        BtrfsOpts(raid="invalid", hdsize=100)


def test_zfs_opts_invalid_checksum():
    with pytest.raises(ValidationError):
        ZfsOpts(raid="raid1", checksum="bad", compress="lz4")


def test_lvm_opts_negative_swapsize():
    with pytest.raises(ValidationError):
        LvmOpts(swapsize=-1)


def _minimal_valid_kwargs(model_class: type) -> dict[str, Any]:
    if model_class is Global:
        return valid_global()
    if model_class is Network:
        return valid_network()
    if model_class is ZfsOpts:
        return valid_zfs_opts()
    if model_class is LvmOpts:
        return {"hdsize": 100, "swapsize": 1, "maxroot": 1, "maxvz": 1, "minfree": 1}
    if model_class is BtrfsOpts:
        return {"raid": "raid1", "hdsize": 100, "compress": "off"}
    if model_class is DiskSetup:
        return valid_disk_setup()
    if model_class is PostInstallationWebhook:
        return valid_post_installation_webhook()
    if model_class is FirstBoot:
        return valid_first_boot()
    return {}


# https://docs.pytest.org/en/stable/how-to/parametrize.html#parametrize
@pytest.mark.parametrize(
    "model_class, field, value",
    [
        (Global, "keyboard", "{{keyboard}}"),
        (Global, "country", "{{country}}"),
        (Global, "fqdn", "{{fqdn}}"),
        (Global, "mailto", "{{mailto}}"),
        (Global, "timezone", "{{timezone}}"),
        (Global, "root_password", "{{root_password}}"),
        (Global, "root_ssh_keys", ["{{root_ssh_keys}}"]),
        (Global, "reboot_on_error", "{{reboot_on_error}}"),
        (Global, "reboot_mode", "{{reboot_mode}}"),
        (Network, "source", "{{source}}"),
        (Network, "cidr", "{{cidr}}"),
        (Network, "dns", "{{dns}}"),
        (Network, "gateway", "{{gateway}}"),
        (Network, "filter", "{{filter}}"),
        (ZfsOpts, "raid", "{{raid}}"),
        (ZfsOpts, "ashift", "{{ashift}}"),
        (ZfsOpts, "arc_max", "{{arc_max}}"),
        (ZfsOpts, "checksum", "{{checksum}}"),
        (ZfsOpts, "compress", "{{compress}}"),
        (ZfsOpts, "copies", "{{copies}}"),
        (ZfsOpts, "hdsize", "{{hdsize}}"),
        (LvmOpts, "hdsize", "{{hdsize}}"),
        (LvmOpts, "swapsize", "{{swapsize}}"),
        (LvmOpts, "maxroot", "{{maxroot}}"),
        (LvmOpts, "maxvz", "{{maxvz}}"),
        (LvmOpts, "minfree", "{{minfree}}"),
        (BtrfsOpts, "raid", "{{raid}}"),
        (BtrfsOpts, "hdsize", "{{hdsize}}"),
        (BtrfsOpts, "compress", "{{compress}}"),
        (DiskSetup, "filesystem", "{{filesystem}}"),
        (DiskSetup, "disk_list", ["{{disk_list}}"]),
        (DiskSetup, "filter", "{{filter}}"),
        (DiskSetup, "filter_match", "{{filter_match}}"),
        (PostInstallationWebhook, "url", "{{url}}"),
        (PostInstallationWebhook, "cert_fingerprint", "{{cert_fingerprint}}"),
        (FirstBoot, "source", "{{source}}"),
        (FirstBoot, "ordering", "{{ordering}}"),
        (FirstBoot, "url", "{{url}}"),
        (FirstBoot, "cert_fingerprint", "{{cert_fingerprint}}"),
    ],
)
# parametrized test to check each field in each model accepts a placeholder value
# https://docs.pytest.org/en/stable/how-to/parametrize.html#parametrize
def test_accepts_placeholder(
    model_class: type,
    field: str,
    value: Any,
):
    """Test that each model field accepts a placeholder value."""
    kwargs: dict[str, Any] = _minimal_valid_kwargs(model_class)
    kwargs[field] = value
    if model_class is Global:
        _handle_global_placeholders(kwargs, field)
    if model_class is DiskSetup:
        _handle_disksetup_placeholders(kwargs, field)
    # Should not raise
    model_class(**kwargs)


# internal helper functions for the test above
def _handle_global_placeholders(kwargs: dict[str, Any], field: str):
    # Always ensure exactly one of root_password or root_password_hashed is present
    if field == "root_password":
        kwargs.pop("root_password_hashed", None)
    elif field == "root_password_hashed":
        kwargs.pop("root_password", None)
    else:
        # For all other fields, ensure root_password is present and root_password_hashed is not
        if "root_password" not in kwargs and "root_password_hashed" not in kwargs:
            kwargs["root_password"] = "StrongP@ssw0rd!"
        elif "root_password" in kwargs and "root_password_hashed" in kwargs:
            kwargs.pop("root_password_hashed", None)


def _handle_disksetup_placeholders(kwargs: dict[str, Any], field: str):
    if field == "zfs":
        kwargs.pop("lvm", None)
        kwargs.pop("btrfs", None)
    elif field == "lvm":
        kwargs.pop("zfs", None)
        kwargs.pop("btrfs", None)
    elif field == "btrfs":
        kwargs.pop("zfs", None)
        kwargs.pop("lvm", None)
