from logging import getLogger
from utm.__main__ import CmdResult, run_command_async

LOGGER = getLogger("utm.proxmox.system")


async def get_system_memory_gb() -> int:
    cmd = ["free", "-g"]
    result: CmdResult = await run_command_async(*cmd)
    output = result.stdout or ""
    for line in output.splitlines():
        if "Mem:" in line:
            parts = line.split()
            if len(parts) >= 2:
                return int(parts[1])
    return 0


async def get_cpu_cores() -> int:
    result: CmdResult = await run_command_async("nproc")
    output = result.stdout or ""
    try:
        return int(output.strip())
    except ValueError:
        return 0


async def get_disk_size_gb() -> int:
    cmd = ["df", "-BG", "--output=size", "/"]
    result: CmdResult = await run_command_async(*cmd)
    output = result.stdout.strip().splitlines()
    if len(output) >= 2:
        try:
            size_str = output[1].strip().rstrip("G")
            return int(size_str)
        except ValueError:
            return 0
    return 0


async def find_pci_nics() -> list[str]:
    """Return PCI NIC device IDs for add-in cards only (exclude onboard bus 00)."""
    result: CmdResult = await run_command_async("lspci", "-Dn")
    output = result.stdout or ""

    nics: list[str] = []
    for line in output.splitlines():
        if "0200" in line:  # class code for Ethernet controller
            pci_id = line.split()[0]
            nics.append(pci_id)

    if not nics:
        return []

    filtered: list[str] = []
    for pci in nics:
        try:
            bus = int(pci.split(":")[1], 16)
            if bus > 0:
                filtered.append(pci)
        except Exception:
            continue

    return filtered if filtered else nics


async def load_vfio_kernel_modules() -> bool:
    """Ensure required vfio kernel modules exist in /etc/modules-load.d/vfio.conf."""
    vfio_conf = "/etc/modules-load.d/vfio.conf"
    vfio_modules = ["vfio", "vfio_pci", "vfio_iommu_type1", "vfio_virqfd"]

    result: CmdResult = await run_command_async("bash", "-c", f"cat {vfio_conf} 2>/dev/null || true", check=False)
    if result.returncode != 0:
        LOGGER.error(f"Failed to read {vfio_conf}: {result.stderr}")
        return False

    existing = set(result.stdout.strip().splitlines()) if result.stdout else set()  # type: ignore
    missing = [m for m in vfio_modules if m not in existing]

    if not missing:
        LOGGER.info("All VFIO kernel modules already configured for loading")
        return True

    modules_str = "\n".join(missing)
    result = await run_command_async("bash", "-c", f"echo -e '{modules_str}' >> {vfio_conf}", check=False)
    if result.returncode != 0:
        LOGGER.error(f"Failed to update {vfio_conf}: {result.stderr}")
        return False

    LOGGER.info(f"Added missing VFIO modules to {vfio_conf}: {', '.join(missing)}")
    return True


async def blacklist_host_driver_for_pci_id(pci_id: str) -> bool:
    """Blacklist the kernel driver currently bound to the given PCI device ID."""
    cmd_get_driver = [
        "bash",
        "-c",
        f"lspci -nnk -s {pci_id} | grep 'Kernel driver in use' | awk '{{print $5}}'",
    ]
    result: CmdResult = await run_command_async(*cmd_get_driver, check=False)
    if result.returncode != 0:
        LOGGER.error(f"Failed to get driver for PCI ID {pci_id}: {result.stderr}")
        return False

    driver = result.stdout.strip()
    if not driver:
        LOGGER.error(f"No kernel driver found for PCI ID {pci_id}")
        return False

    blacklist_file = f"/etc/modprobe.d/blacklist-{driver}.conf"

    cmd_check = [
        "bash",
        "-c",
        f"grep -q '^blacklist {driver}$' {blacklist_file} 2>/dev/null",
    ]
    check_result = await run_command_async(*cmd_check, check=False)
    if check_result.returncode == 0:
        LOGGER.info(f"Driver {driver} already blacklisted ({blacklist_file})")
        return True

    cmd_blacklist = ["bash", "-c", f"echo 'blacklist {driver}' > {blacklist_file}"]
    result = await run_command_async(*cmd_blacklist, check=False)
    if result.returncode != 0:
        LOGGER.error(f"Failed to blacklist driver {driver} for PCI ID {pci_id}: {result.stderr}")
        return False

    LOGGER.info(f"Blacklisted driver {driver} for PCI ID {pci_id}")
    return True


async def bind_pci_ids_to_vfio(pci_ids: list[str]) -> bool:
    """Ensure given PCI IDs are bound to vfio-pci driver."""
    if not pci_ids:
        LOGGER.warning("No PCI IDs provided for vfio-pci binding")
        return False

    vfio_conf = "/etc/modprobe.d/vfio-pci.conf"

    cmd_read = [
        "bash",
        "-c",
        r"grep -oP '(?<=ids=)[^\s]+' /etc/modprobe.d/vfio-pci.conf 2>/dev/null || true",
    ]
    result: CmdResult = await run_command_async(*cmd_read, check=False)
    existing_ids = result.stdout.strip().split(",") if result.stdout.strip() else []

    new_ids = sorted(set(existing_ids + pci_ids))
    ids_str = ",".join(new_ids)

    if set(existing_ids) == set(new_ids):
        LOGGER.info(f"All PCI IDs {pci_ids} already bound to vfio-pci")
        return True

    cmd_write = ["bash", "-c", f"echo 'options vfio-pci ids={ids_str}' > {vfio_conf}"]
    result = await run_command_async(*cmd_write, check=False)
    if result.returncode != 0:
        LOGGER.error(f"Failed to bind PCI NICs to vfio-pci: {result.stderr}")
        return False

    LOGGER.info(f"Bound PCI NICs {ids_str} to vfio-pci driver")
    return True
