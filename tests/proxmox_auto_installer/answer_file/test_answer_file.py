import re
import pytest
from pydantic import ValidationError
from proxmox_auto_installer.answer_file import (
    DiskConfig,
    GlobalConfig,
    NetworkConfig,
    ProxmoxAnswerFile,
    DISK_CONFIG_DEFAULTS,
    GLOBAL_CONFIG_DEFAULTS,
    NETWORK_CONFIG_DEFAULTS,
)


@pytest.fixture
def valid_global_config():
    return GlobalConfig(
        keyboard=GLOBAL_CONFIG_DEFAULTS["keyboard"],
        country=GLOBAL_CONFIG_DEFAULTS["country"],
        timezone=GLOBAL_CONFIG_DEFAULTS["timezone"],
        fqdn=GLOBAL_CONFIG_DEFAULTS["fqdn"],
        mailto=GLOBAL_CONFIG_DEFAULTS["mailto"],
        root_password_hashed=GLOBAL_CONFIG_DEFAULTS["root_password_hashed"],
    )


@pytest.fixture
def valid_network_config():
    return NetworkConfig(
        hostname="pve1",
        interface="eth0",
        cidr="192.168.1.10/24",
        gateway="192.168.1.1",
        dns="8.8.8.8",
    )


@pytest.fixture
def valid_disk_config():
    return DiskConfig(filesystem="ext4", disk_list=["/dev/sda"])


# --- Core Tests ---
def test_full_valid_answer_file(valid_global_config, valid_network_config, valid_disk_config):
    answer_file = ProxmoxAnswerFile(
        global_config=valid_global_config,
        network=valid_network_config,
        disk_setup=valid_disk_config,
    )
    serialized = answer_file.to_dict()

    # Check top-level keys
    assert set(serialized.keys()) == {"global", "network", "disk-setup"}

    # TOML serialization: keys should not be quoted
    toml_str = answer_file.to_toml_str()
    assert not re.search(r'^".*"\s*=', toml_str, flags=re.MULTILINE)


def test_to_json_and_pretty_json(valid_global_config, valid_network_config, valid_disk_config):
    answer_file = ProxmoxAnswerFile(
        global_config=valid_global_config,
        network=valid_network_config,
        disk_setup=valid_disk_config,
    )

    json_str = answer_file.to_json()
    pretty_json_str = answer_file.to_pretty_json()

    assert '"global"' in json_str
    assert '"disk-setup"' in json_str
    assert '"network"' in json_str
    assert pretty_json_str.startswith("{\n")


def test_invalid_missing_fields_raises_error(valid_network_config, valid_disk_config):
    with pytest.raises(ValidationError):
        ProxmoxAnswerFile(
            network=valid_network_config,
            disk_setup=valid_disk_config,
        )


def test_default_answer_file_creation():
    answer_file = ProxmoxAnswerFile(
        global_config=GlobalConfig(),
        network=NetworkConfig(),
        disk_setup=DiskConfig(),
    )

    g = answer_file.global_config
    assert g.keyboard == GLOBAL_CONFIG_DEFAULTS["keyboard"]
    assert g.country == GLOBAL_CONFIG_DEFAULTS["country"]
    assert g.timezone == GLOBAL_CONFIG_DEFAULTS["timezone"]
    assert g.fqdn == GLOBAL_CONFIG_DEFAULTS["fqdn"]
    assert g.mailto == GLOBAL_CONFIG_DEFAULTS["mailto"]
    assert g.root_password_hashed == GLOBAL_CONFIG_DEFAULTS["root_password_hashed"]

    n = answer_file.network
    assert n.source == NETWORK_CONFIG_DEFAULTS["source"]
    assert n.cidr == NETWORK_CONFIG_DEFAULTS["cidr"]
    assert n.gateway == NETWORK_CONFIG_DEFAULTS["gateway"]
    assert n.dns == NETWORK_CONFIG_DEFAULTS["dns"]

    d = answer_file.disk_setup
    assert d.filesystem == DISK_CONFIG_DEFAULTS["filesystem"]
    assert d.disk_list == DISK_CONFIG_DEFAULTS["disk_list"]
    assert d.zfs_raid == DISK_CONFIG_DEFAULTS["zfs_raid"]
