from ipaddress import ip_address, ip_network
from safe_pc.proxmox_auto_installer.constants import PROXMOX_ALLOWED_NETWORK_SOURCES
from pydantic import BaseModel, Field, field_validator


"""
        "network": {
            "source": "from-answer",
            "cidr": "10.0.4.238/24",
            "gateway": "10.0.4.1",
            "dns": "10.0.4.1",
            "filter.ID_NET_NAME_MAC": f"*{mgmt_nic}".replace(":", ""),
        },

"""


hex_vals = "0123456789abcdefABCDEF"


class NetworkConfig(BaseModel):
    source: str = Field(
        default="from-answer",
        Required=True,
        description="Network configuration source",
        example="from-answer",
        regex="^(from-dhcp|from-answer)$",
    )
    cidr: str | None = Field(
        default="10.0.4.238/24",
        description="CIDR notation for IP address and subnet mask",
        example="10.0.4.238/24",
        regex=r"^(\d{1,3}\.){3}\d{1,3}/\d{1,2}$",
    )
    gateway: str | None = Field(
        default="10.0.4.1",
        description="Gateway IP address",
        example="10.0.4.1",
        regex=r"^(\d{1,3}\.){3}\d{1,3}$",
    )
    dns: str | None = Field(
        default="10.0.4.1",
        description="DNS server IP address(es), comma-separated",
        example="10.0.4.1",
        regex=r"^(\d{1,3}\.){3}\d{1,3}(,(\d{1,3}\.){3}\d{1,3})*$",
    )
    mac_filter: str = Field(
        default="",
        Required=True,
        description="Management NIC MAC address for filter",
        example="00:11:22:33:44:55",
        regex=r"^\*([0-9a-fA-F]{2}:?){6}$",
        alias="filter.ID_NET_NAME_MAC",
    )

    # validate each field
    @field_validator("source")
    def validate_source(cls, source_value):
        if source_value not in PROXMOX_ALLOWED_NETWORK_SOURCES:
            raise ValueError(f"Invalid network source: {source_value}")
        return source_value

    @field_validator("cidr", "gateway", "dns", mode="before")
    def validate_network_fields(cls, value, info):
        source = info.data.get("source")
        if source == "from-answer":
            if value is None:
                raise ValueError(
                    f"{info.field_name} is required when source is 'from-answer'"
                )
        else:
            if value is not None:
                raise ValueError(
                    f"{info.field_name} must be None when source is not 'from-answer'"
                )
        return value

    # validate that the cidr is a valid IP network
    @field_validator("cidr")
    def validate_cidr(cls, cidr_value, info):
        source = info.data.get("source")
        if source == "from-answer" and cidr_value:
            try:
                ip_network(cidr_value, strict=False)
            except ValueError:
                raise ValueError(f"Invalid CIDR notation: {cidr_value}")
        return cidr_value

    # validate that the gateway is in the same subnet as the cidr
    @field_validator("gateway")
    def validate_gateway_in_subnet(cls, gateway_value, info):
        source = info.data.get("source")
        cidr = info.data.get("cidr")
        if source == "from-answer" and cidr and gateway_value:
            network = ip_network(cidr, strict=False)
            gateway_ip = ip_address(gateway_value)
            if gateway_ip not in network:
                raise ValueError(f"Gateway {gateway_value} is not in the subnet {cidr}")
        return gateway_value

    # validate that each DNS server is a valid IP address
    @field_validator("dns")
    def validate_dns_ips(cls, dns_value, info):
        source = info.data.get("source")
        if source == "from-answer" and dns_value:
            dns_ips = [ip.strip() for ip in dns_value.split(",")]
            for ip in dns_ips:
                try:
                    ip_address(ip)
                except ValueError:
                    raise ValueError(f"Invalid DNS IP address: {ip}")
        return dns_value

    # validate the mgmt_nic_mac is a valid MAC address format
    @field_validator("mgmt_nic_mac")
    def validate_mgmt_nic_mac(cls, mac_value):
        if not mac_value.startswith("*"):
            mac_value = "*" + mac_value
        mac = mac_value[1:]
        if ":" in mac:
            parts = mac.split(":")
            if len(parts) != 6 or not all(
                len(part) == 2 and all(c in hex_vals for c in part) for part in parts
            ):
                raise ValueError(f"Invalid MAC address format: {mac_value}")
        else:
            if len(mac) != 12 or not all(c in hex_vals for c in mac):
                raise ValueError(f"Invalid MAC address format: {mac_value}")
        return mac_value
