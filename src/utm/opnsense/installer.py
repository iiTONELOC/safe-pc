from asyncio import sleep
from logging import getLogger

from utm.utils.console_driver import ConsoleDriver
from utm.proxmox.vms import stop_vm, get_vm_status
from utm.__main__ import run_command_async, setup_logging
from utm.opnsense.xml_template_sync import xml_template_sync
from utm.opnsense.pexpect_drivers import drive_installer, drive_configurator  # type: ignore


logout_time_mins = 10
base_prefix = "[OPNSense Installer] "
logout_time_secs = logout_time_mins * 60
logger = getLogger("utm.opnsense.installer")

DEFAULT_ROOT_PASSWORD = "UseBetterPassword!23"


async def _set_correct_boot_remove_iso(vm_id: str) -> None:
    """Set the correct boot order and remove the installation ISO after installation.

    Restarts the VM after making the changes.

    Args:
        vm_id (str): The Proxmox VM ID
    """
    await stop_vm(vm_id)

    logger.info(f"{base_prefix}Setting VM ID {vm_id} to boot from its hard disk.")
    await run_command_async(*["qm", "set", vm_id, "--boot", "order=scsi0"], check=True)

    logger.info(f"{base_prefix}Removing installation ISO from VM ID {vm_id}.")
    await run_command_async(*["qm", "set", vm_id, "--scsi1", "none"], check=True)

    # ensure the vm is set to boot when proxmox starts
    logger.info(f"{base_prefix}Enabling boot on startup for VM ID {vm_id}.")
    await run_command_async(*["qm", "set", vm_id, "--onboot", "1"], check=True)

    return None


async def install_opnsense(vm_id: str, root_password: str = DEFAULT_ROOT_PASSWORD) -> bool:
    try:
        async with ConsoleDriver(int(vm_id), logger, base_prefix) as console:
            await drive_installer(console.child, root_password)  # type: ignore
            logger.info(f"{base_prefix}OPNsense installation completed for VM ID {vm_id}.")
            await _set_correct_boot_remove_iso(vm_id)
            return True

    except Exception as e:
        logger.error(f"{base_prefix}Error during installation: {e}")
        return False

    return False


async def post_install_interface_config(vm_id: str, root_password: str = DEFAULT_ROOT_PASSWORD) -> bool:
    try:
        async with ConsoleDriver(int(vm_id), logger, base_prefix) as console:
            # configure the machine here after it rebooted
            while True:
                try:
                    status_cmd = await get_vm_status(vm_id)
                    if "status: running" in status_cmd:
                        break
                    await sleep(2.5)
                except Exception:
                    await sleep(2.5)
            logger.info(f"{base_prefix}Starting post-install configuration for VM ID {vm_id}.")
            await drive_configurator(console.child, root_password)  # type: ignore
            return True
    except Exception as e:
        logger.error(f"{base_prefix}Error during post-install configuration: {e}")
    return False


async def runner(vm_id: str, root_password: str = DEFAULT_ROOT_PASSWORD) -> None:
    steps = [
        ("Installing OPNsense", install_opnsense),
        ("Post-install configuration", post_install_interface_config),
        ("Merging SafeSense XML template", xml_template_sync),
    ]
    index = 0
    for step_name, step_func in steps:
        logger.info(f"{base_prefix}Starting step: {step_name}")
        success = await step_func(vm_id, root_password)
        # if its not the last step, we need to wait between steps
        if index < len(steps) - 1:
            index += 1
            await sleep(10)  # give the system some time to register its off
        if not success:
            logger.error(f"{base_prefix}Step failed: {step_name}")
            return
        logger.info(f"{base_prefix}Completed step: {step_name}")


def main():
    from asyncio import run
    from os import environ

    setup_logging()
    # DO NOT USE THE DEFAULT ROOT PASSWORD IN PRODUCTION ENVIRONMENTS
    run(runner("100", environ.get("SAFE_SENSE_PWD", None) or DEFAULT_ROOT_PASSWORD))


if __name__ == "__main__":
    main()
