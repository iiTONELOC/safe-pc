import pytest
from pydantic import ValidationError
from safe_pc.proxmox_auto_installer.answer_file.network import (
    NetworkConfig,
    NETWORK_CONFIG_DEFAULTS,
)


# --- Defaults & Valid ---
def test_network_defaults():
    cfg = NetworkConfig()
    assert cfg.source == NETWORK_CONFIG_DEFAULTS["source"]
    assert cfg.cidr == NETWORK_CONFIG_DEFAULTS["cidr"]
    assert cfg.gateway == NETWORK_CONFIG_DEFAULTS["gateway"]
    assert cfg.dns == NETWORK_CONFIG_DEFAULTS["dns"]
    assert cfg.mac_filter == NETWORK_CONFIG_DEFAULTS["mac_filter"]


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
    cfg = NetworkConfig(mac_filter=NETWORK_CONFIG_DEFAULTS["mac_filter"])
    dumped = cfg.model_dump(by_alias=True)
    assert "filter.ID_NET_NAME_MAC" in dumped
    assert dumped["filter.ID_NET_NAME_MAC"] == NETWORK_CONFIG_DEFAULTS["mac_filter"]

    cfg = NetworkConfig()
    assert cfg.source == NETWORK_CONFIG_DEFAULTS["source"]
    assert cfg.cidr == NETWORK_CONFIG_DEFAULTS["cidr"]
    assert cfg.gateway == NETWORK_CONFIG_DEFAULTS["gateway"]
    assert cfg.dns == NETWORK_CONFIG_DEFAULTS["dns"]
    assert cfg.mac_filter == NETWORK_CONFIG_DEFAULTS["mac_filter"]


# --- Invalid Inputs ---
@pytest.mark.parametrize("invalid_source", ["invalid", "", None])
def test_network_config_invalid_source(invalid_source):
    with pytest.raises(ValidationError):
        NetworkConfig(source=invalid_source)


@pytest.mark.parametrize(
    "invalid_cidr",
    [
        "not_a_cidr",
        "300.1.1.1/24",
        "192.168.1.1",
        "192.168.1.1/33",
        "192.168.1.256/24",
        "192.168.1.-1/24",
        "255.255.255.255/24",
        "",
    ],
)
def test_network_config_invalid_cidr(invalid_cidr):
    with pytest.raises(ValidationError):
        NetworkConfig(cidr=invalid_cidr)


@pytest.mark.parametrize(
    "invalid_gateway",
    [
        "not_an_ip",
        "251.1.1.1",
        "255.255.255.255",
        "",
    ],
)
def test_network_config_invalid_gateway(invalid_gateway):
    with pytest.raises(ValidationError):
        NetworkConfig(gateway=invalid_gateway)


@pytest.mark.parametrize(
    "invalid_dns",
    [
        "not_an_ip",
        "192.168.1.1, 8.8.8.8",  # spaces
        "192.168.1.1,192.168.1.1",  # duplicates
        "192.168.1.1,",  # trailing comma
        "",
    ],
)
def test_network_config_invalid_dns(invalid_dns):
    with pytest.raises(ValidationError):
        NetworkConfig(dns=invalid_dns)


@pytest.mark.parametrize(
    "invalid_mac",
    [
        "notamac",
        "*GG:HH:II:JJ:KK:LL",
        "*00:11:22:33:44",
        "*00:11:22:33:44:55:66",
        "",
    ],
)
def test_network_config_invalid_mac(invalid_mac):
    with pytest.raises(ValidationError):
        NetworkConfig(mac_filter=invalid_mac)


def test_gateway_set_to_net_address_raises():
    with pytest.raises(ValidationError):
        NetworkConfig(cidr="192.168.1.0/24", gateway="192.168.1.0")


# --- Conditionals and norms ---
def test_mac_without_star_is_normalized():
    cfg = NetworkConfig(mac_filter="00:11:22:33:44:55")
    assert cfg.mac_filter == "*00:11:22:33:44:55"


def test_from_dhcp_sets_fields_none():
    cfg = NetworkConfig(source="from-dhcp", cidr=None, gateway=None, dns=None)
    assert cfg.source == "from-dhcp"
    assert cfg.cidr is None
    assert cfg.gateway is None
    assert cfg.dns is None
