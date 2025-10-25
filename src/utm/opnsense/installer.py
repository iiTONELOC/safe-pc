from asyncio import sleep
from logging import getLogger

from utm.utils.console_driver import ConsoleDriver
from utm.proxmox.vms import stop_vm, get_vm_status
from utm.__main__ import run_command_async, setup_logging
from utm.utils.utils import send_key_to_pexpect_proc, strip_ansi_escape_sequences  # type: ignore

from pexpect import spawn as pe_spawn, TIMEOUT, EOF  # type: ignore

logger = getLogger("utm.opnsense.install_and_configure")


logout_time_mins = 10
base_prefix = "[OPNSense Installer] "
logout_time_secs = logout_time_mins * 60


async def set_correct_boot_remove_iso(vm_id: str) -> None:
    """Set the correct boot order and remove the installation ISO after installation.

    Restarts the VM after making the changes.

    Args:
        vm_id (str): The Proxmox VM ID
    """
    await stop_vm(vm_id)
    tries = 0
    while tries < 10:
        status_cmd = await get_vm_status(vm_id)
        if "status: stopped" in status_cmd:
            break
        tries += 1
        await sleep(2.5)

    logger.info(f"{base_prefix}Setting VM ID {vm_id} to boot from its hard disk.")
    await run_command_async(*["qm", "set", vm_id, "--boot", "order=scsi0"], check=True)

    logger.info(f"{base_prefix}Removing installation ISO from VM ID {vm_id}.")
    await run_command_async(*["qm", "set", vm_id, "--scsi1", "none"], check=True)

    logger.info(f"{base_prefix}Starting VM ID {vm_id} after installation.")
    await run_command_async(*["qm", "start", vm_id], check=True)


async def drive_installer(child: pe_spawn, root_password: str = "UseBetterPassword!23") -> None:  # type: ignore
    buffer = ""
    pwd_confirmed = False
    while True:
        try:
            # Output is inconsistent, read it in chunks in a non-blocking manner
            chunk = child.read_nonblocking(size=2048, timeout=2)  # type: ignore
            buffer += chunk  # type: ignore
            screen_buffer = strip_ansi_escape_sequences(buffer)  # type: ignore

            await sleep(1)

            if "Welcome to the OPNSense installer" in screen_buffer:
                send_key_to_pexpect_proc("enter", child)
                buffer = ""

            elif "login:" in screen_buffer:
                child.send("installer\r")
                buffer = ""

            elif (
                "Choose one of the following tasks" in screen_buffer
                or "stripe  Stripe - No Redundancy" in screen_buffer
                or "Keymap Selection" in screen_buffer
            ):
                await sleep(2)
                send_key_to_pexpect_proc("enter", child)
                buffer = ""

            elif "Please select one or more disks to create a zpool" in screen_buffer:
                await sleep(2)
                if "*" not in screen_buffer:
                    child.send(" ")
                    await sleep(0.3)
                send_key_to_pexpect_proc("enter", child)
                buffer = ""

            elif "Password:" in screen_buffer and "Root Password" not in screen_buffer:
                child.send("opnsense\r")
                buffer = ""

            elif "Last Chance!" in screen_buffer:
                await sleep(1)
                send_key_to_pexpect_proc("tab", child)
                await sleep(0.5)
                send_key_to_pexpect_proc("enter", child)
                buffer = ""

            elif "Root Password" in screen_buffer and "Change root password" in screen_buffer:
                await sleep(1)
                if not pwd_confirmed:
                    send_key_to_pexpect_proc("enter", child)
                    await sleep(1)
                    child.send(root_password + "\r")
                    await sleep(1)
                    child.send(root_password + "\r")
                    pwd_confirmed = True
                    buffer = ""
                else:
                    send_key_to_pexpect_proc("down", child)
                    await sleep(0.5)
                    send_key_to_pexpect_proc("enter", child)
                    await sleep(0.5)
                    send_key_to_pexpect_proc("enter", child)
                    buffer = ""

            elif "The installation finished successfully" in screen_buffer:
                await sleep(1)
                send_key_to_pexpect_proc("ctrl_c", child)
                send_key_to_pexpect_proc("ctrl_O", child)
                buffer = ""
                break

        except TIMEOUT:
            continue
        except EOF:
            break


async def opnsense_installer(vm_id: str, root_password: str = "UseBetterPassword!23") -> None:
    try:
        async with ConsoleDriver(int(vm_id), logger, base_prefix) as console:
            await drive_installer(console.child, root_password)  # type: ignore
    except Exception as e:
        logger.error(f"{base_prefix}Error during installation: {e}")

    logger.info(f"{base_prefix}Installation process completed, shutting down VM ID {vm_id}.")
    await set_correct_boot_remove_iso(vm_id)


if __name__ == "__main__":
    import asyncio

    setup_logging()
    asyncio.run(opnsense_installer("100", "StrongPassword123"))
