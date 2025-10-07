import pytest
import re
from pydantic import ValidationError
from safe_pc.proxmox_auto_installer.answer_file.disk import DiskConfig
from safe_pc.proxmox_auto_installer.answer_file._global import GlobalConfig
from safe_pc.proxmox_auto_installer.answer_file.network import NetworkConfig
from safe_pc.proxmox_auto_installer.answer_file.answer_file import ProxmoxAnswerFile


@pytest.fixture
def valid_global_config():
    return GlobalConfig(
        keyboard="en-us",
        country="US",
        timezone="America/New_York",
        fqdn="proxmox.lab.local",
        mailto="root@localhost",
        root_password_hashed="$6$rounds=656000$12345678$" + "A" * 86,
    )


@pytest.fixture
def valid_network_config():
    return NetworkConfig(
        hostname="pve1",
        interface="eth0",
        cidr="192.168.1.10/24",
        gateway="192.168.1.1",
        dns_server="8.8.8.8",
    )


@pytest.fixture
def valid_disk_config():
    return DiskConfig(filesystem="ext4", disk_list=["/dev/sda"])


def test_full_valid_answer_file(
    valid_global_config, valid_network_config, valid_disk_config
):
    answer_file = ProxmoxAnswerFile(
        global_config=valid_global_config,
        network=valid_network_config,
        disk_setup=valid_disk_config,
    )
    serialized = answer_file.to_dict()

    # alias keys should appear
    assert "global" in serialized
    assert "disk-setup" in serialized
    assert "network" in serialized

    # round trip TOML should contain non-quoted keys
    toml_str = answer_file.to_toml_str()
    assert not re.search(r'^".*"\s*=', toml_str, flags=re.MULTILINE)


def test_to_json_and_pretty_json(
    valid_global_config, valid_network_config, valid_disk_config
):
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


#  TODO: Add more tests
