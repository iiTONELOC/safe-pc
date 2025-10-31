from os import path
from logging import getLogger
from utm.__main__ import run_command_async, CmdResult

logger = getLogger("utm.proxmox.vms")


async def get_vm_status(vm_id: str) -> str:
    """Get the current status of a Proxmox VM."""
    result: CmdResult = await run_command_async("qm", "status", vm_id)
    return result.stdout.strip()


async def start_vm(vm_id: str) -> None:
    """Start a Proxmox VM."""
    await run_command_async("qm", "start", vm_id)


async def stop_vm(vm_id: str) -> None:
    """Stop a Proxmox VM."""
    await run_command_async("qm", "stop", vm_id)


async def restart_vm(vm_id: str) -> None:
    """Restart a Proxmox VM."""
    await run_command_async("qm", "reboot", vm_id)


async def reset_vm(vm_id: str) -> None:
    """Reset a Proxmox VM."""
    await run_command_async("qm", "reset", vm_id)


async def delete_vm(vm_id: str) -> None:
    """Delete a Proxmox VM."""
    await run_command_async("qm", "destroy", vm_id)


async def delete_vm_and_disks(vm_id: str) -> None:
    """Delete a Proxmox VM and its disks."""
    await run_command_async("qm", "destroy", vm_id, "--destroy-unreferenced-disks", "1")


def get_vm_serial_socket_path(vm_id: str, serial_port: int = 0) -> str:
    """Get the serial socket path for a Proxmox VM."""
    socket_path = f"/var/run/qemu-server/{vm_id}.serial{serial_port}" if vm_id else ""
    if not path.exists(socket_path):
        logger.error(f"Serial socket not found at {socket_path}")
        raise FileNotFoundError(f"Serial socket not found at {socket_path}")
    return socket_path


async def vm_start_if_not_running(vm_id: str) -> None:
    """Start the VM if it is not already running."""
    status = await get_vm_status(vm_id)
    if "status: running" not in status:
        logger.info(f"Starting VM ID {vm_id}. Current status: {status}")
        await start_vm(vm_id)
