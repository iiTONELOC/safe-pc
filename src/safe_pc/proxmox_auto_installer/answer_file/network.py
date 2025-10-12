from re import compile as re_compile
from ipaddress import ip_address, ip_network
from pydantic import BaseModel, Field, field_validator
from safe_pc.proxmox_auto_installer.constants import PROXMOX_ALLOWED_NETWORK_SOURCES

HEX = "0123456789abcdefABCDEF"
SOURCE_FROM_ANSWER = "from-answer"

SOURCE_PATTERN = re_compile(r"^(from-dhcp|from-answer)$")
CIDR_PATTERN = re_compile(r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$")
IP_PATTERN = re_compile(r"^(\d{1,3}\.){3}\d{1,3}$")
DNS_PATTERN = re_compile(r"^(\d{1,3}\.){3}\d{1,3}(,(\d{1,3}\.){3}\d{1,3})*$")
MAC_PATTERN = re_compile(r"^\*?[0-9A-Fa-f]{12}$")

NETWORK_CONFIG_DEFAULTS = {
    "source": SOURCE_FROM_ANSWER,
    "cidr": "10.0.4.238/24",
    "gateway": "10.0.4.1",
    "dns": "10.0.4.1",
    "mac_filter": "*bc241129f843",
}


class NetworkConfig(BaseModel):
    model_config = {"populate_by_name": True}

    source: str = Field(
        default=NETWORK_CONFIG_DEFAULTS["source"],
        description="Network configuration source",
        pattern=SOURCE_PATTERN.pattern,
    )
    cidr: str | None = Field(
        default=NETWORK_CONFIG_DEFAULTS["cidr"],
        description="CIDR notation for IP address and subnet mask",
        pattern=CIDR_PATTERN.pattern,
    )
    gateway: str | None = Field(
        default=NETWORK_CONFIG_DEFAULTS["gateway"],
        description="Gateway IP address",
        pattern=IP_PATTERN.pattern,
    )
    dns: str | None = Field(
        default=NETWORK_CONFIG_DEFAULTS["dns"],
        description="DNS server IP address(es), comma-separated",
        pattern=DNS_PATTERN.pattern,
    )
    mac_filter: str = Field(
        default=NETWORK_CONFIG_DEFAULTS["mac_filter"],
        description="Management NIC MAC address for filter",
        alias="filter.ID_NET_NAME_MAC",
        pattern=MAC_PATTERN.pattern,
    )

    @field_validator("source")
    def validate_source(cls, v: str) -> str:
        if not SOURCE_PATTERN.match(v):
            raise ValueError(f"Invalid source pattern: {v}")
        if v not in PROXMOX_ALLOWED_NETWORK_SOURCES:
            raise ValueError(f"Invalid network source: {v}")
        return v

    @field_validator("cidr", "gateway", "dns")
    def enforce_required_fields(cls, v, info):# type: ignore
        source_value = info.data.get("source")# type: ignore
        required = info.field_name in {"cidr", "gateway", "dns"}# type: ignore
        if source_value == SOURCE_FROM_ANSWER:
            if required and (v is None or v == ""):
                raise ValueError(
                    f"{info.field_name} is required when source is '{SOURCE_FROM_ANSWER}'"# type: ignore
                )
        elif v is not None:
            raise ValueError(
                f"{info.field_name} must be None when source is not '{SOURCE_FROM_ANSWER}'"# type: ignore
            )
        return v # type: ignore

    @field_validator("cidr", mode="before")
    def validate_cidr(cls, v: str | None, info):# type: ignore
        if info.data.get("source") != SOURCE_FROM_ANSWER:# type: ignore
            return v
        if not v:
            raise ValueError("CIDR cannot be empty when source is 'from-answer'")
        if not CIDR_PATTERN.match(v):
            raise ValueError(f"Invalid CIDR pattern: {v}")
        try:
            net = ip_network(v, strict=False)
            addr = ip_address(v.split("/")[0])
            if (
                addr.is_multicast
                or addr.is_reserved
                or addr.is_loopback
                or addr.is_unspecified
                or not addr.is_private
                or addr == net.network_address
                or addr == net.broadcast_address
                or addr not in net
            ):
                raise ValueError(f"CIDR address {addr} is not a valid host address")
        except ValueError:
            raise ValueError(f"Invalid CIDR notation: {v}")
        return v

    @field_validator("gateway")
    def validate_gateway(cls, v: str | None, info):# type: ignore
        if info.data.get("source") != SOURCE_FROM_ANSWER:# type: ignore
            return v
        if not v or not IP_PATTERN.match(v):
            raise ValueError(f"Invalid gateway: {v}")
        cidr_value = info.data.get("cidr")# type: ignore
        if not cidr_value:
            raise ValueError("CIDR must be set when source is 'from-answer'")
        net = ip_network(cidr_value, strict=False) # type: ignore
        gw = ip_address(v)
        if (
            gw not in net
            or gw == net.network_address
            or gw == net.broadcast_address
            or gw.is_multicast
            or gw.is_reserved
            or gw.is_loopback
            or gw.is_unspecified
        ):
            raise ValueError(f"Gateway {v} is not a valid host in subnet {cidr_value}")
        return v

    @field_validator("dns")
    def validate_dns(cls, v: str | None, info): # type: ignore
        if info.data.get("source") != SOURCE_FROM_ANSWER or not v: # type: ignore
            return v
        if not DNS_PATTERN.match(v):
            raise ValueError(f"Invalid DNS pattern: {v}")
        seen = set() #type: ignore
        for ip_str in v.split(","):
            ip_str = ip_str.strip()
            if ip_str in seen:
                raise ValueError(f"Duplicate DNS IP address: {ip_str}")
            try:
                ip_address(ip_str)
            except ValueError:
                raise ValueError(f"Invalid DNS IP address: {ip_str}")
            seen.add(ip_str) # type: ignore
        return v

    @field_validator("mac_filter")
    def validate_mac_filter(cls, v: str):
        if not v or v.strip() == "":
            raise ValueError("MAC filter cannot be empty")
        normalized = v if v.startswith("*") else "*" + v
        if not MAC_PATTERN.fullmatch(normalized):
            raise ValueError(f"Invalid MAC address format: {normalized}")
        return normalized
