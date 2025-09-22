#!/bin/sh
# This script discovers the fastest non removable storage and the on-board nic to be used in the
# auto installer

DISK=""
MGMT=""
ONBOARD_NICS=""
DNS_IP="10.0.4.1"
GATEWAY_IP="10.0.4.1"
PROXMOX_IP="10.0.4.254/24"
CONFIG_SERVER="http://10.0.4.2:5000/api/device_discovery"


find_disk_by_criteria() {
  required_rota="$1"  # can be "" for any, or 0/1
  for dev in /sys/block/*; do
    name=$(basename "$dev")
    # ignore loop, ram, floppy, cdrom
    case "$name" in loop*|ram*|fd*|sr*) continue ;; esac

    size_kb=$(cat "$dev/size")
    size_gb=$(( size_kb / 2 / 1024 / 1024 ))
    rota=$(cat "$dev/queue/rotational")
    removable=$(cat "$dev/removable")
    # must be non-removable and at least 20GB
    if [ "$removable" -eq 0 ] && [ "$size_gb" -ge 20 ]; then
    # match rota if specified
      if [ -z "$required_rota" ] || [ "$rota" -eq "$required_rota" ]; then
        echo "$name"
        return 0
      fi
    fi
  done
  return 1
}


find_fastest_disk() {
  chosen=""

  # Prefer non-removable SSD/NVMe (ROTA=0) ≥20GB
  chosen=$(find_disk_by_criteria 0)

  # Fallback: HDD (ROTA=1) ≥20GB
  if [ -z "$chosen" ]; then
    chosen=$(find_disk_by_criteria 1)
  fi

  # Last resort: any non-removable disk ≥20GB
  if [ -z "$chosen" ]; then
    chosen=$(find_disk_by_criteria "")
  fi

  echo "$chosen"
}

DISK="/dev/$(find_fastest_disk)"

# 2. Find the on-board NIC to be used for management
# udev onboard tags
for nic in /sys/class/net/*; do
  name=$(basename "$nic")

  # skip loopback
  [ "$name" = "lo" ] && continue

  # skip virtual NICs
  devpath=$(readlink -f /sys/class/net/$name)
  echo "$devpath" | grep -q "/devices/virtual/net/" && continue

  # query the udev db for properties and check for onboard tag
  if udevadm info -q property -p "/sys/class/net/$name" 2>/dev/null | grep -q '^ID_NET_NAME_ONBOARD='; then
    ONBOARD_NICS="$ONBOARD_NICS$name\n"
  fi
done

# chipset-root heuristic (only if udev found nothing)
if [ -z "$(printf "%b" "$ONBOARD_NICS" | sed '/^$/d')" ]; then
  # look for NICs
  for nic in /sys/class/net/*; do
    name=$(basename "$nic")

    # skip loopback
    [ "$name" = "lo" ] && continue

    # skip virtual NICs
    devpath=$(readlink -f /sys/class/net/$name)
    echo "$devpath" | grep -q "/devices/virtual/net/" && continue

    # skip if no device (e.g. bridge, bond, etc)
    [ ! -e "$nic/device" ] && continue

    # resolve full device path
    devpath=$(readlink -f "$nic/device")

    # check if PCI address starts with 0000:00: and likely isn't a pcie slot (no physical_slot file)
    if echo "$devpath" | grep -q "0000:00:" && [ ! -s "$devpath/physical_slot" ]; then
      ONBOARD_NICS="$ONBOARD_NICS$name\n"
    fi
  done
fi

# exit if a disk wasn't found
if [ -z "$DISK" ]; then
  echo "ERROR: No suitable disk found" >&2
  exit 1
fi

# Pick first onboard NIC
MGMT=$(printf "%b" "$ONBOARD_NICS" | sed '/^$/d' | head -n1)

# exit if a nic wasn't found
if [ -z "$MGMT" ]; then
  echo "ERROR: No onboard NIC found" >&2
  exit 1
fi

# Bring link up
ip link set dev "$MGMT" up
ip addr add $PROXMOX_IP dev "$MGMT"
ip route add default via $GATEWAY_IP
echo "nameserver $GATEWAY_IP" > /etc/resolv.conf

# Call config server(curl is not in the initrd, so using wget)
RESPONSE=$(wget -qO- \
  --header="Content-Type: application/json" \
  --post-data="{\"disk\":\"$DISK\",\"mgmt_nic\":\"$MGMT\"}" \
  "$CONFIG_SERVER" \
  --server-response 2>&1 | awk '/^  HTTP/{print $2}' | tail -1)

if [ "$RESPONSE" -ne 200 ]; then
  echo "ERROR: Failed to contact config server" >&2
  echo "HTTP code: $RESPONSE" >&2
  cat /tmp/resp.json >&2
  exit 1
fi

exit 0
