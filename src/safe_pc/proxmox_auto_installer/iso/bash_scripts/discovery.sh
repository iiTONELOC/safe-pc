#!/bin/sh
# This script discovers the fastest non removable storage and the on-board nic to be used in the
# auto installer

DISK=""
MGMT=""
ONBOARD_NICS=""
ANSWER_FILE="/tmp/answer.toml"


find_disk_by_criteria() {
    required_rota="$1"  # can be "" for any, or 0/1
    smallest_name=""
    smallest_size_gb=""
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
                if [ -z "$smallest_name" ] || [ "$size_gb" -lt "$smallest_size_gb" ]; then
                    smallest_name="$name"
                    smallest_size_gb="$size_gb"
                fi
            fi
        fi
    done
    if [ -n "$smallest_name" ]; then
        echo "$smallest_name"
        return 0
    fi
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

# get its MAC address
MGMT_MAC=$(cat /sys/class/net/$MGMT/address)
if [ -z "$MGMT_MAC" ]; then
  echo "ERROR: Failed to get MAC address for $MGMT" >&2
  exit 1
fi


if [ -f "$ANSWER_FILE" ]; then
  sed -i.bak \
  # look for the following line in the answer file and replace it
  -e "s|^\s*filter\.ID_NET_NAME_MAC\s*=\s*\"[^\"]*\"|filter.ID_NET_NAME_MAC = \"*$MGMT_MAC\"|" \
  # find the disk-list line and replace it with the discovered disk
  -e "s|^\s*disk-list\s*=\s*\[[^]]*\]|disk-list = [\"$DISK\"]|" \
  "$ANSWER_FILE"
fi

# if it doesnt exist, echo a warning but continue
if [ ! -f "$ANSWER_FILE" ]; then
  echo "WARNING: Answer file $ANSWER_FILE not found, skipping update" >&2
fi

echo "Discovery complete. Disk: $DISK, Mgmt NIC: $MGMT ($MGMT_MAC)"
exit 0