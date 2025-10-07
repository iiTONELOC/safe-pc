import pytest
from pydantic import ValidationError
from safe_pc.proxmox_auto_installer.answer_file.network import NetworkConfig


def test_network_defaults():
    cfg = NetworkConfig()
    assert cfg.source == "from-answer"
    assert cfg.cidr == "10.0.4.238/24"
    assert cfg.gateway == "10.0.4.1"
    assert cfg.dns == "10.0.4.1"
    assert cfg.mac_filter == "*00:11:22:33:44:55"


def test_network_config_valid():
    cfg = NetworkConfig(
        source="from-answer",
        cidr="192.168.1.100/24",
        gateway="192.168.1.1",
        dns="192.168.1.1,1.1.1.1",
        mac_filter="*AA:BB:CC:DD:EE:FF",
    )
    assert cfg.source == "from-answer"
    assert cfg.cidr == "192.168.1.100/24"
    assert cfg.gateway == "192.168.1.1"
    assert cfg.dns == "192.168.1.1,1.1.1.1"
    assert cfg.mac_filter == "*AA:BB:CC:DD:EE:FF"


def test_network_config_alias_serialization():
    cfg = NetworkConfig(mac_filter="*00:11:22:33:44:55")
    dumped = cfg.model_dump(by_alias=True)
    assert "filter.ID_NET_NAME_MAC" in dumped
    assert dumped["filter.ID_NET_NAME_MAC"] == "*00:11:22:33:44:55"
    cfg = NetworkConfig()
    assert cfg.source == "from-answer"
    assert cfg.cidr == "10.0.4.238/24"
    assert cfg.gateway == "10.0.4.1"
    assert cfg.dns == "10.0.4.1"
    assert cfg.mac_filter == "*00:11:22:33:44:55"


def test_network_config_invalid_source():
    with pytest.raises(ValidationError):
        NetworkConfig(source="invalid")


def test_network_config_invalid_cidr():
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="not_a_cidr")
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="300.1.1.1/24")
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="192.168.1.1")
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="192.168.1.1/33")
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="192.168.1.256/24")
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="192.168.1.-1/24")
    with pytest.raises(expected_exception=ValidationError):
        NetworkConfig(cidr="255.255.255.255/24")


def test_network_config_invalid_gateway():
    with pytest.raises(ValidationError):
        NetworkConfig(gateway="not_an_ip")
    with pytest.raises(ValidationError):
        NetworkConfig(gateway="251.1.1.1")
    with pytest.raises(ValidationError):
        NetworkConfig(gateway="255.255.255.255")


def test_network_config_invalid_dns():
    with pytest.raises(ValidationError):
        NetworkConfig(dns="not_an_ip")


def test_network_config_invalid_mac():
    with pytest.raises(ValidationError):
        NetworkConfig(mac_filter="notamac")
    with pytest.raises(ValidationError):
        NetworkConfig(mac_filter="*GG:HH:II:JJ:KK:LL")


def test_invalid_source_empty():
    with pytest.raises(ValidationError):
        NetworkConfig(source="")


def test_invalid_cidr_empty():
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="")


def test_invalid_gateway_empty():
    with pytest.raises(ValidationError):
        NetworkConfig(gateway="")


def test_invalid_dns_empty():
    with pytest.raises(ValidationError):
        NetworkConfig(dns="")


def test_empty_mac_filter_is_not_allowed():
    with pytest.raises(ValidationError):
        NetworkConfig(mac_filter="")


def test_gateway_set_to_net_address_raises():
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="192.168.1.0/24", gateway="192.168.1.0")


def test_dns_with_spaces_raises():
    with pytest.raises(ValidationError):
        NetworkConfig(dns="192.168.1.1, 8.8.8.8")


def test_dns_with_duplicates_raises():
    with pytest.raises(ValidationError):
        NetworkConfig(dns="192.168.1.1,192.168.1.1")


def test_dns_with_trailing_comma_raises():
    with pytest.raises(ValidationError):
        NetworkConfig(dns="192.168.1.1,")


def test_mac_missing_octets_raises():
    with pytest.raises(ValidationError):
        NetworkConfig(mac_filter="*00:11:22:33:44")


def test_mac_extra_octets_raises():
    with pytest.raises(ValidationError):
        NetworkConfig(mac_filter="*00:11:22:33:44:55:66")


def test_source_none_raises():
    with pytest.raises(ValidationError):
        NetworkConfig(source=None)
