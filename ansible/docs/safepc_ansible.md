# SAFE PC: Ansible Documentation

## Address Space

```sh
# Management LAN
10.3.8.0/24

# Internal LAN
10.30.8.0/24
```

### Address Assignments

#### Management LAN

| Host       | Address  | Notes                      |
| ---------- | -------- | -------------------------- |
| Proxmox VE | 10.3.8.1 | Should be the on-board NIC |

#### Internal LAN

| Host        | Address   | Notes                                                                           |
| ----------- | --------- | ------------------------------------------------------------------------------- |
| OPNSense FW | 10.30.8.1 | Should be a removable PCIe NIC (preferably Intel) that supports PCI passthrough |

#### WAN

| Host        | Address   | Notes                                                                           |
| ----------- | --------- | ------------------------------------------------------------------------------- |
| OPNSense FW | DHCP, ISP | Should be a removable PCIe NIC (preferably Intel) that supports PCI passthrough |
