# Firewall LAN IP configuration
# change these only if they conflict with an existing network
export SAFE_LAN_PREFIX="${SAFE_LAN_PREFIX:-192.168.1}"
export SAFE_LAN_BIT_COUNT="${SAFE_LAN_BIT_COUNT:-24}"
export SAFE_LAN_FW_HOST="${SAFE_LAN_FW_HOST:-${SAFE_LAN_PREFIX}.254}"
export SAFE_SENSE_PWD="${SAFE_SENSE_PWD:-UseBetterPassword!23}"

# Proxmox username - default is root
export PROX_USER="${PROX_USER:-root}"

# Proxmox management interface configuration
# Configuration settings for the out-of-band management interface
export PROX_CIDR="${PROX_CIDR:-192.168.1.253/24}"
export PROX_GATEWAY="${PROX_GATEWAY:-192.168.1.254}"
export PROX_DNS="${PROX_DNS:-192.168.1.253}"
export PROX_TZ="${PROX_TZ:-America/New_York}"

# Host with Answer File
# IP address for the machine serving the answer file, required by the
# Proxmox installer.
export HOST_IP="${HOST_IP:-10.0.4.2}"