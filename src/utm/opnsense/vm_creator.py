from os import environ
from logging import getLogger

from utm.opnsense.iso.constants import OpnSenseConstants
from utm.proxmox.iommu import configure_for_pci_passthrough
from utm.utils.utils import handle_keyboard_interrupt
from utm.__main__ import (
    CmdResult,
    is_production,
    setup_logging,
    set_env_variable,
    run_command_async,
)
from utm.proxmox.system import (
    get_cpu_cores,
    find_pci_nics,
    get_disk_size_gb,
    get_system_memory_gb,
    bind_pci_ids_to_vfio,
    load_vfio_kernel_modules,
    blacklist_host_driver_for_pci_id,
)

existing_num = 0
logger = getLogger("utm.opnsense.vm_creator")


async def get_system_resources():
    cpu_cores = await get_cpu_cores()
    memory_gb = await get_system_memory_gb()
    disk_size_gb = await get_disk_size_gb()
    pci_nics = await find_pci_nics()
    return cpu_cores, memory_gb, disk_size_gb, pci_nics


async def does_production_fw_exist() -> bool:
    # check if the production firewall VM exists
    result: CmdResult = await run_command_async(*["qm", "list"], check=False)
    output = result.stdout if result.stdout else ""
    global existing_num
    for line in output.splitlines():
        if "safe-sense" in line:
            existing_num += 1
    return existing_num > 0


async def handle_pasthrough_configuration(pci_nics: list[str]):
    iommu_enabled = await configure_for_pci_passthrough()
    if not iommu_enabled:
        logger.error("IOMMU is not enabled after configuration attempt.")
        return

    for pci_id in pci_nics:
        await blacklist_host_driver_for_pci_id(pci_id)
    await load_vfio_kernel_modules()
    await bind_pci_ids_to_vfio(pci_nics)
    await run_command_async("update-initramfs", "-u", "-k", "all", check=False)

    set_env_variable("CAPSTONE_PASSTHROUGH_CONFIGURED", "1", system_wide=True)

    logger.info("PCI passthrough configured. Rebooting to apply.")
    await run_command_async("/usr/sbin/reboot", check=False)


def get_create_vm_command(fw_name: str, vm_id: int, cpu_cores: int, memory_gb: int) -> list[str]:
    return [
        "qm",
        "create",
        str(vm_id),
        "--name",
        fw_name,
        "--memory",
        str(memory_gb * 1024),
        "--balloon",
        "0",
        "--cores",
        str(cpu_cores),
        "--sockets",
        "1",
        "--cpu",
        "host",
        "--bios",
        "seabios",
        "--machine",
        "q35",
        "--scsihw",
        "virtio-scsi-pci",
        "--boot",
        "order=scsi0",
        "--serial0",
        "socket",
        "--vga",
        "serial0",
    ]


def get_appropriate_resources(cpu_cores: int, memory_gb: int, disk_size_gb: int) -> tuple[int, int, int]:
    # enforces mins of 2 cores, 8GB RAM, 40GB disk space
    # looks for a max of 85% cpu cores and RAM, and with 64GB disk space

    if cpu_cores < 3:
        logger.warning("CPU has less than 3 cores; allocating all available cores to VM.")
        vm_cpu_cores = cpu_cores
    elif cpu_cores < 2:
        raise ValueError("Not enough CPU cores to create OPNsense VM.")
    else:
        vm_cpu_cores = max(3, int(cpu_cores * 0.85))

    if memory_gb < 12:
        logger.warning("System has less than 12GB RAM; allocating 90%% of available RAM to VM.")
        vm_memory_gb = max(8, int(memory_gb * 0.90))
    elif memory_gb < 8:
        raise ValueError("System memory is too low to create OPNsense VM.")
    else:
        vm_memory_gb = max(12, int(memory_gb * 0.85))

    if disk_size_gb < 64:
        logger.warning("Disk size is less than 64GB; allocating 90%% of available disk to VM.")
        vm_disk_size_gb = max(40, int(disk_size_gb * 0.90))
    elif disk_size_gb < 40:
        raise ValueError("Disk size is too small to create OPNsense VM.")
    else:
        vm_disk_size_gb = 64

    return vm_cpu_cores, vm_memory_gb, vm_disk_size_gb


def filter_pci_nics(pci_nics: list[str]) -> list[str]:
    filtered_pci_nics: list[str] = []
    seen_devices: set[str] = set()

    for pci_id in pci_nics:
        # Split into domain, bus, device.function
        # Example: 0000:03:00.1 -> domain=0000, bus=03, dev_func=00.1
        parts = pci_id.split(":")
        if len(parts) != 3:
            continue  # skip malformed entries

        domain_bus = ":".join(parts[:2])  # "0000:03"
        device = parts[2].split(".")[0]  # "00"
        key = f"{domain_bus}:{device}"  # "0000:03:00"

        if key not in seen_devices:
            seen_devices.add(key)
            filtered_pci_nics.append(pci_id)

    return filtered_pci_nics


async def create_new_opnsense_vm(
    fw_name: str,
    vm_id: int,
    vm_cpu_cores: int,
    vm_memory_gb: int,
    vm_disk_size_gb: int,
    pci_nics: list[str],
    is_prod: bool,
):

    result: CmdResult = await run_command_async(
        *get_create_vm_command(fw_name, vm_id, vm_cpu_cores, vm_memory_gb),
        check=False,
    )
    if result.returncode != 0:
        logger.error(f"Failed to create OPNsense VM: {result.stderr}")
        return False

    # create disk
    result: CmdResult = await run_command_async(
        *[
            "zfs",
            "create",
            "-V",
            f"{vm_disk_size_gb}G",
            "-o",
            "volblocksize=16K",
            "-o",
            "compression=lz4",
            f"rpool/vm-data/vm-{vm_id}-disk-0",
        ],
        check=False,
    )
    if result.returncode != 0:
        logger.error(f"Failed to create disk for OPNsense VM: {result.stderr}")
        return False

    # attach disk
    result: CmdResult = await run_command_async(
        *[
            "qm",
            "set",
            str(vm_id),
            "--scsihw",
            "virtio-scsi-pci",
            "--scsi0",
            f"zfs-vm-data:vm-{vm_id}-disk-0,size={vm_disk_size_gb}G,ssd=1,discard=on",
        ],
        check=False,
    )

    # Check for disk creation errors
    if result.returncode != 0:
        logger.error(f"Failed to create and attach disk for OPNsense VM: {result.stderr}")
        return False

    # import the OPNsense ISO (really an IMG) as a disk
    await run_command_async(
        *[
            "qm",
            "importdisk",
            str(vm_id),
            f"/var/lib/vz/template/iso/OPNsense-{OpnSenseConstants.CURRENT_VERSION}-serial-amd64.iso",
            "local-zfs",
        ],
        check=False,
    )

    # attach the disk, set it to boot
    result: CmdResult = await run_command_async(
        *[
            "qm",
            "set",
            str(vm_id),
            "--scsihw",
            "virtio-scsi-pci",
            "--scsi1",
            f"local-zfs:vm-{vm_id}-disk-0",
            "--boot",
            "order=scsi1;scsi0",
        ],
        check=False,
    )
    if result.returncode != 0:
        logger.error(f"Failed to attach ISO to OPNsense VM: {result.stderr}")
        return False

    # Attach first PCI NICs
    filtered = filter_pci_nics(pci_nics)
    for idx, pci_id in enumerate(filtered):
        # Drop the .function part to pass through all functions (e.g., 0000:01:00)
        pci_base = pci_id.rsplit(".", 1)[0]
        pci_opts = f"{pci_base},pcie=1"

        result: CmdResult = await run_command_async(
            *[
                "qm",
                "set",
                str(vm_id),
                f"--hostpci{idx}={pci_opts}",
            ],
            check=False,
        )

        if result.returncode != 0:
            logger.error(f"Failed to attach PCI NIC {pci_id}: {result.stderr}")
            return False
    # Enable autostart for production VM
    if is_prod:
        result: CmdResult = await run_command_async(
            *[
                "qm",
                "set",
                str(vm_id),
                "--startup",
                "order=1,up=10,down=10",
            ],
            check=False,
        )
        if result.returncode != 0:
            logger.warning(f"Failed to enable autostart for {fw_name}: {result.stderr}")
        else:
            logger.info(f"Autostart enabled for {fw_name}.")

    logger.info(f"OPNsense VM '{fw_name}' created and NICs attached successfully.")


async def create_opnsense_vm():
    # Determine environment and target VM name
    is_prod = is_production()
    prod_exists = await does_production_fw_exist()
    fw_name = "safe-sense" if is_prod else f"safe-sense-{existing_num + 100}"

    if is_prod and prod_exists:
        logger.info("Production firewall VM already exists. Skipping creation.")
        return True

    logger.info(f"Creating OPNsense VM: {fw_name}")

    # Gather system resources
    cpu_cores, memory_gb, disk_size_gb, pci_nics = await get_system_resources()

    logger.info(
        f"System has {cpu_cores} CPU cores, {memory_gb} GB RAM, {disk_size_gb} GB disk, "
        f"and {len(pci_nics)} PCI NICs."
    )

    # Passthrough configuration (only runs once)
    if environ.get("CAPSTONE_PASSTHROUGH_CONFIGURED", "0") != "1":
        if len(pci_nics) < 2:
            logger.error("Not enough PCI NICs for OPNsense VM (need at least 2).")
            return False

        if cpu_cores < 2 or memory_gb < 8 or disk_size_gb < 64:
            logger.error("System does not meet minimum specs for OPNsense VM.")
            return False

        await handle_pasthrough_configuration(pci_nics)
        return True  # stop here, host is rebooting

    logger.info("PCI passthrough already configured. Proceeding to VM creation.")

    # Allocate 85% of available resources, respecting minimums
    vm_cpu_cores, vm_memory_gb, vm_disk_size_gb = get_appropriate_resources(cpu_cores, memory_gb, disk_size_gb)

    logger.info(
        f"Cores allocated to VM: {vm_cpu_cores}. Memory allocated to VM: {vm_memory_gb} GB. Disk allocated to VM: {vm_disk_size_gb} GB."
    )

    vm_id = existing_num + 100
    await create_new_opnsense_vm(
        fw_name,
        vm_id,
        vm_cpu_cores,
        vm_memory_gb,
        vm_disk_size_gb,
        pci_nics,
        is_prod,
    )

    return True


async def run():
    setup_logging()
    await create_opnsense_vm()


@handle_keyboard_interrupt
def main():
    import asyncio

    asyncio.run(run())


if __name__ == "__main__":
    main()
