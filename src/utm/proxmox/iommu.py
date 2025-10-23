from pathlib import Path
from logging import getLogger
from aiofiles import open as aio_open
from utm.__main__ import CmdResult, run_command_async

logger = getLogger("utm.proxmox.iommu")


async def enable_pci_in_grub():
    grub_file = Path("/etc/default/grub")
    if grub_file.exists():
        async with aio_open(grub_file, mode="r") as f:
            grub_contents = await f.readlines()

        for i, line in enumerate(grub_contents):
            if line.startswith("GRUB_CMDLINE_LINUX_DEFAULT"):
                if "intel_iommu=on" not in line and "amd_iommu=on" not in line:
                    line = line.strip().rstrip('"') + ' intel_iommu=on amd_iommu=on"\n'
                    grub_contents[i] = line
                    logger.info("  Enabled IOMMU in GRUB configuration.")
                break

        async with aio_open(grub_file, mode="w") as f:
            await f.writelines(grub_contents)

        await run_command_async("update-grub")
        logger.info("  Updated GRUB configuration for IOMMU. Reboot required.")


async def configure_for_pci_passthrough() -> bool:
    """
    Ensure Proxmox is configured for PCI Passthrough by checking if IOMMU is enabled.
    Returns True if IOMMU is enabled, False otherwise.
    """
    cmd = [
        "dmesg",
    ]
    logger.info("Checking if IOMMU is enabled in the system...")
    result: CmdResult = await run_command_async(*cmd, check=False)
    output = result.stdout if result.stdout else ""
    iommu_enabled = False
    for line in output.splitlines():
        if "IOMMU enabled" in line or "VT-d" in line or "AMD-Vi" in line:
            iommu_enabled = True
            break

    # if not enabled, enable it in GRUB
    if not iommu_enabled:
        logger.info("  IOMMU is not enabled. Enabling IOMMU...")
        await enable_pci_in_grub()
        # reboot is required
        logger.info("  IOMMU not enabled, system will reboot to apply changes.")
        await run_command_async("reboot", check=False)
    else:
        logger.info("  IOMMU is already enabled.")

    return iommu_enabled
