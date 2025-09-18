#!/bin/sh
# This script discovers the fastest non removable storage and the on-board nic to be used in the auto installer
ONBOARD_NICS=""

# 1. Find the fastest non-removal disk >= 20gb
# Try SSD/NVMe first (ROTA=0)
DISK=$(lsblk -dn -o NAME,SIZE,ROTA | awk '$2+0 >= 20 && $3==0 {print $1; exit}')

# If none found, fall back to HDD (ROTA=1)
if [ -z "$DISK" ]; then
    DISK=$(lsblk -dn -o NAME,SIZE,ROTA | awk '$2+0 >= 20 && $3==1 {print $1; exit}')
fi

# Still nothing? Just grab the first >=20 GB disk no matter what
if [ -z "$DISK" ]; then
    DISK=$(lsblk -dn -o NAME,SIZE | awk '$2+0 >= 20 {print $1; exit}')
fi

# Prefix with /dev/ so installer sees full path
DISK="/dev/$DISK"

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

# Output the discovered disk and nic
echo "Using disk: $DISK"
echo "Using management NIC: $MGMT"
