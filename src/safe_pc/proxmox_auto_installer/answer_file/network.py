from calendar import c
from re import compile as re_compile
from ipaddress import ip_address, ip_network
from pydantic import BaseModel, Field, field_validator
from safe_pc.proxmox_auto_installer.constants import PROXMOX_ALLOWED_NETWORK_SOURCES

HEX = "0123456789abcdefABCDEF"

SOURCE_PATTERN = re_compile(r"^(from-dhcp|from-answer)$")
CIDR_PATTERN = re_compile(r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$")
IP_PATTERN = re_compile(r"^(\d{1,3}\.){3}\d{1,3}$")
DNS_PATTERN = re_compile(r"^(\d{1,3}\.){3}\d{1,3}(,(\d{1,3}\.){3}\d{1,3})*$")
MAC_PATTERN = re_compile(
    r"^\*(?:[0-9A-Fa-f]{12}|(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})$"
)


class NetworkConfig(BaseModel):
    model_config = {"populate_by_name": True}
    source: str = Field(
        default="from-answer",
        description="Network configuration source",
        pattern=SOURCE_PATTERN.pattern,
    )
    cidr: str | None = Field(
        default="10.0.4.238/24",
        description="CIDR notation for IP address and subnet mask",
        pattern=CIDR_PATTERN.pattern,
    )
    gateway: str | None = Field(
        default="10.0.4.1",
        description="Gateway IP address",
        pattern=IP_PATTERN.pattern,
    )
    dns: str | None = Field(
        default="10.0.4.1",
        description="DNS server IP address(es), comma-separated",
        pattern=DNS_PATTERN.pattern,
    )
    mac_filter: str = Field(
        default="*00:11:22:33:44:55",
        description="Management NIC MAC address for filter",
        alias="filter.ID_NET_NAME_MAC",
        pattern=MAC_PATTERN.pattern,
    )

    @field_validator("source")
    def validate_source(cls, source_value: str) -> str:
        if not SOURCE_PATTERN.match(source_value):
            raise ValueError(f"Invalid source pattern: {source_value}")
        if source_value not in PROXMOX_ALLOWED_NETWORK_SOURCES:
            raise ValueError(f"Invalid network source: {source_value}")
        return source_value

    @field_validator("cidr", "gateway", "dns")
    def enforce_required_fields(cls, field_value, info):
        """
        Enforces required/None depending on source type.
        """
        source_value = info.data.get("source")
        if source_value == "from-answer":
            if field_value is None or field_value == "":
                raise ValueError(
                    f"{info.field_name} is required when source is 'from-answer'"
                )
        else:
            if field_value is not None:
                raise ValueError(
                    f"{info.field_name} must be None when source is not 'from-answer'"
                )
        return field_value

    @field_validator("cidr", mode="before")
    def validate_cidr(cls, cidr_value: str | None, info):
        if not cidr_value and info.data.get("source") == "from-answer":
            raise ValueError("CIDR cannot be empty when source is 'from-answer'")
        if cidr_value and info.data.get("source") == "from-answer":
            if len(cidr_value.split("/")) != 2:
                raise ValueError(f"CIDR must contain a '/' character: {cidr_value}")
            if not CIDR_PATTERN.match(cidr_value):
                raise ValueError(f"Invalid CIDR pattern: {cidr_value}")
            try:
                space = ip_network(cidr_value, strict=False)
                # ensure that the address isnt the network, broadcast, gateway, etc
                addr = ip_address(cidr_value.split("/")[0])
                if (
                    addr.is_multicast
                    or addr.is_reserved
                    or addr.is_loopback
                    or addr.is_unspecified
                    or addr.is_private is False
                    or addr == space.network_address
                    or addr == space.broadcast_address
                    or addr not in space
                ):
                    raise ValueError(
                        f"CIDR address {cidr_value.split('/')[0]} is not a valid host address"
                    )
            except ValueError:
                raise ValueError(f"Invalid CIDR notation: {cidr_value}")
        return cidr_value

    @field_validator("gateway")
    def validate_gateway(cls, gateway_value: str | None, info):
        source_value = info.data.get("source")
        if source_value == "from-answer":
            if gateway_value is None or gateway_value == "":
                raise ValueError("Gateway cannot be empty when source is 'from-answer'")

            if IP_PATTERN.match(gateway_value) is None:
                raise ValueError(f"Invalid gateway pattern: {gateway_value}")
            cidr_value = info.data.get("cidr")
            if cidr_value:
                network = ip_network(cidr_value, strict=False)
                gateway_ip = ip_address(gateway_value)
                if (
                    gateway_ip not in network
                    or gateway_ip == network.network_address
                    or gateway_ip == network.broadcast_address
                    or gateway_ip.is_multicast
                    or gateway_ip.is_reserved
                    or gateway_ip.is_loopback
                    or gateway_ip.is_unspecified
                ):
                    raise ValueError(
                        f"Gateway {gateway_value} is not a valid host in subnet {cidr_value}"
                    )

            else:
                raise ValueError("CIDR must be set when source is 'from-answer'")

        return gateway_value

    @field_validator("dns")
    def validate_dns(cls, dns_value: str | None, info):
        source_value = info.data.get("source")
        seen = set()
        if dns_value and source_value == "from-answer":
            if not DNS_PATTERN.match(dns_value):
                raise ValueError(f"Invalid DNS pattern: {dns_value}")
            for dns_ip in dns_value.split(","):
                if dns_ip in seen:
                    raise ValueError(f"Duplicate DNS IP address: {dns_ip}")
                try:
                    ip_address(dns_ip.strip())
                    seen.add(dns_ip)
                except ValueError:
                    raise ValueError(f"Invalid DNS IP address: {dns_ip}")
        return dns_value

    @field_validator(
        "mac_filter",
    )
    def validate_mac_filter(cls, mac_filter_value: str):
        if not mac_filter_value or mac_filter_value.strip() == "":
            raise ValueError("MAC filter cannot be empty")

        normalized = (
            mac_filter_value
            if mac_filter_value.startswith("*")
            else "*" + mac_filter_value
        )
        if not MAC_PATTERN.fullmatch(normalized):
            raise ValueError(f"Invalid MAC address format: {normalized}")
        return normalized
