#!/usr/bin/python3.13
import os
import asyncio
from sys import argv
from pathlib import Path
from logging import getLogger
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

logger = getLogger(__name__)

script_path = Path(argv[0]).resolve()

PROJECT_ROOT = script_path.parent.parent
POETRY_PATH = "/root/.local/share/pipx/venvs/poetry/bin/poetry"


@dataclass
class CmdResult:
    stdout: str
    stderr: str
    returncode: int | None


class CommandError(RuntimeError):
    def __init__(self, args: Sequence[str], rc: int | None, stdout: str, stderr: str):
        super().__init__(f"Command failed ({rc}): {' '.join(map(str, args))}")
        self.args_list = list(args)
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


async def run_command_async(
    *args: str | Path,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> CmdResult:
    cmd = tuple(str(a) for a in args)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await proc.communicate()
    except (asyncio.CancelledError, asyncio.TimeoutError):
        proc.kill()
        await proc.communicate()
        raise
    rc = proc.returncode
    stdout = stdout_b.decode(errors="replace")
    stderr = stderr_b.decode(errors="replace")
    if check and rc != 0:
        raise CommandError(cmd, rc, stdout, stderr)
    return CmdResult(stdout, stderr, rc)


async def is_proxmox() -> bool:
    cmd = "pveversion"
    result = await run_command_async(cmd)
    return result.returncode == 0


def only_on_proxmox(func):  # type: ignore
    async def wrapper(*args, **kwargs):  # type: ignore
        if not await is_proxmox():
            logger.info(f"Not running on Proxmox, skipping {func.__name__}.")  # type: ignore
            return
        return await func(*args, **kwargs)  # type: ignore

    return wrapper  # type: ignore


def remove_enterprise_repo():
    repo_file = Path("/etc/apt/sources.list.d/pve-enterprise.sources")
    try:
        if repo_file.exists():
            repo_file.unlink()
            logger.info(f"Removed enterprise repository file: {repo_file}")
        else:
            logger.info(f"No enterprise repository file found at: {repo_file}")
    except Exception as e:
        logger.error(f"Failed to remove enterprise repository file: {e}")


def remove_ceph_repo():
    repo_file = Path("/etc/apt/sources.list.d/ceph.sources")
    try:
        if repo_file.exists():
            repo_file.unlink()
            logger.info(f"Removed Ceph repository file: {repo_file}")
        else:
            logger.info(f"No Ceph repository file found at: {repo_file}")
    except Exception as e:
        logger.error(f"Failed to remove Ceph repository file: {e}")


def set_proxmox_repo_to_community():
    # File /etc/apt/sources.list.d/proxmox.sources
    # https://pve.proxmox.com/wiki/Package_Repositories

    repo_str = """
Types: deb
URIs: http://download.proxmox.com/debian/pve
Suites: trixie
Components: pve-no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
    """
    repo_file = Path("/etc/apt/sources.list.d/proxmox.sources")

    try:
        # Backup existing file if it exists
        if repo_file.exists():
            backup_file = repo_file.with_suffix(".backup")
            repo_file.rename(backup_file)
            logger.info(f"Backed up existing repository file to {backup_file}")

        # Write the new repository configuration
        with repo_file.open("w") as f:
            f.write(repo_str.strip() + "\n")
        logger.info(f"Set Proxmox repository to community edition in {repo_file}")

    except Exception as e:
        logger.error(f"Failed to set Proxmox repository: {e}")


async def update_and_upgrade_apt():

    env = {"DEBIAN_FRONTEND": "noninteractive"}
    try:
        await run_command_async("apt", "update", "-y", env=env)
        await run_command_async(
            "apt",
            "full-upgrade",
            "-y",
            "-o",
            "Dpkg::Options::=--force-confnew",
            "-o",
            "Dpkg::Options::=--force-confdef",
            env=env,
        )
        logger.info("Successfully updated and upgraded apt repositories.")
    except CommandError as e:
        logger.error(f"APT update/upgrade failed: {e}")


async def install_pipx():
    result = await run_command_async("apt", "install", "-y", "pipx")
    if result.returncode == 0:
        logger.info("Successfully installed pipx.")
    else:
        raise ValueError(f"Failed to install pipx. Return code: {result.returncode}")


async def install_poetry_via_pipx():
    result = await run_command_async("pipx", "install", "poetry")
    if result.returncode != 0:
        logger.error(f"Failed to install poetry via pipx. Return code: {result.returncode}")
        return

    logger.info("Successfully installed poetry via pipx.")
    await run_command_async("pipx", "ensurepath")

    poetry_bin = os.path.expanduser("~/.local/share/pipx/venvs/poetry/bin")
    path_line = f'PATH="{poetry_bin}:$PATH"'

    # Decide where to add the PATH depending on privilege level
    if os.geteuid() == 0:
        # running as root → edit /etc/environment safely
        env_file = "/etc/environment"
        add_path_cmd = f"grep -qxF '{path_line}' {env_file} || echo '{path_line}' >> {env_file}"
        logger.info("Adding Poetry path to /etc/environment (root mode).")
    else:
        # non-root → modify user shell profile instead
        env_file = os.path.expanduser("~/.bashrc")
        add_path_cmd = f"grep -qxF 'export {path_line}' {env_file} || " + f"echo 'export {path_line}' >> {env_file}"
        logger.info("Adding Poetry path to ~/.bashrc (user mode).")

    await run_command_async("bash", "-c", add_path_cmd)
    logger.info("Poetry installation and path setup complete.")


async def install_safe_pc():
    result = await run_command_async(f"{POETRY_PATH}", "install", cwd=PROJECT_ROOT)
    if result.returncode == 0:
        logger.info("Successfully installed SAFE PC via poetry.")
    else:
        raise ValueError(f"Failed to install SAFE PC via poetry. Return code: {result.returncode}")


async def dl_opnsense_iso():
    result = await run_command_async(f"{POETRY_PATH}", "run", "dl-opnsense-iso", cwd=PROJECT_ROOT)
    if result.returncode == 0:
        logger.info("Successfully downloaded OPNsense ISO.")
    else:
        raise ValueError(f"Failed to download OPNsense ISO. Return code: {result.returncode}")


async def unregister_post_install_service():
    service_file = Path("/etc/systemd/system/safe_pc_post_install.service")
    try:
        if service_file.exists():
            await run_command_async("systemctl", "disable", "safe_pc_post_install.service")
            service_file.unlink()
            await run_command_async("systemctl", "daemon-reload")
            logger.info("Unregistered and removed safe_pc_post_install.service")
        else:
            logger.info("safe_pc_post_install.service does not exist, skipping removal.")
    except Exception as e:
        raise ValueError(f"Failed to unregister post install service: {e}")


post_install_steps = (
    (remove_enterprise_repo, "Removing corporate repo"),
    (remove_ceph_repo, "Removing Ceph repo"),
    (set_proxmox_repo_to_community, "Setting Proxmox repo to community"),
    (update_and_upgrade_apt, "Updating and upgrading apt"),
    (install_pipx, "Installing pipx via pip"),
    (install_poetry_via_pipx, "Installing poetry via pipx"),
    (install_safe_pc, "Installing SAFE PC via poetry"),
    (dl_opnsense_iso, "Downloading OPNsense ISO"),
    (unregister_post_install_service, "Unregistering post install service"),
)


@only_on_proxmox
async def main():
    logger.info("SAFE PC. Proxmox Post Install Script")

    for step in post_install_steps:
        func, description = step
        logger.debug(f"Starting step: {description}")
        try:
            await func() if asyncio.iscoroutinefunction(func) else func()
            logger.debug(f"Completed step: {description}")
        except Exception as e:
            logger.error(f"Error during step '{description}': {e}")
            logger.info("Aborting post installation due to error.")
            exit(1)

    logger.info("Post installation steps completed.")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
    exit(0)
