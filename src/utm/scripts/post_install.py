#!/usr/bin/python3
from pathlib import Path
from logging import getLogger
from dataclasses import dataclass
from collections.abc import Mapping, Sequence

logger = getLogger(__name__)

# Repeated from utils
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


# determine if we are on proxmox or a different os
async def is_proxmox() -> bool:
    cmd = "pveversion"
    result = await run_command_async(cmd)
    return result.returncode == 0


async def remove_enterprise_repo():
    if not await is_proxmox():
        logger.info("Not running on Proxmox, skipping repository removal.")
        return
    repo_file = Path("/etc/apt/sources.list.d/pve-enterprise.sources")
    try:
        if repo_file.exists():
            repo_file.unlink()
            logger.info(f"Removed enterprise repository file: {repo_file}")
        else:
            logger.info(f"No enterprise repository file found at: {repo_file}")
    except Exception as e:
        logger.error(f"Failed to remove enterprise repository file: {e}")
        
    
async def remove_ceph_repo():
    if not await is_proxmox():
        logger.info("Not running on Proxmox, skipping Ceph repository removal.")
        return
    repo_file = Path("/etc/apt/sources.list.d/ceph.sources")
    try:
        if repo_file.exists():
            repo_file.unlink()
            logger.info(f"Removed Ceph repository file: {repo_file}")
        else:
            logger.info(f"No Ceph repository file found at: {repo_file}")
    except Exception as e:
        logger.error(f"Failed to remove Ceph repository file: {e}")
        
        

async def set_proxmox_repo_to_community():
    #File /etc/apt/sources.list.d/proxmox.sources
    #https://pve.proxmox.com/wiki/Package_Repositories
    if not await is_proxmox():
        logger.info("Not running on Proxmox, skipping repository configuration.")
        return
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
            backup_file = repo_file.with_suffix('.backup')
            repo_file.rename(backup_file)
            logger.info(f"Backed up existing repository file to {backup_file}")

        # Write the new repository configuration
        with repo_file.open('w') as f:
            f.write(repo_str.strip() + '\n')
        logger.info(f"Set Proxmox repository to community edition in {repo_file}")
        

    except Exception as e:
        logger.error(f"Failed to set Proxmox repository: {e}")
        
async def update_and_upgrade_apt():
    if not await is_proxmox():
        logger.info("Not running on Proxmox, skipping apt update.")
        return

    env = {"DEBIAN_FRONTEND": "noninteractive"}
    try:
        await run_command_async("apt", "update", "-y", env=env)
        await run_command_async(
            "apt", "full-upgrade", "-y",
            "-o", "Dpkg::Options::=--force-confnew",
            "-o", "Dpkg::Options::=--force-confdef",
            env=env
        )
        logger.info("Successfully updated and upgraded apt repositories.")
    except CommandError as e:
        logger.error(f"APT update/upgrade failed: {e}")
        
        
async def install_pipx_via_pip():
    if not await is_proxmox():
        logger.info("Not running on Proxmox, skipping pipx installation.")
        return
    result = await run_command_async("apt", "install", "-y", "pipx")
    if result.returncode == 0:
        logger.info("Successfully installed pipx.")
    else:
        logger.error(f"Failed to install pipx. Return code: {result.returncode}")
        
async def install_poetry_via_pipx():
    if not await is_proxmox():
        logger.info("Not running on Proxmox, skipping poetry installation.")
        return
    result = await run_command_async("pipx", "install", "poetry")
    if result.returncode == 0:
        logger.info("Successfully installed poetry via pipx.")
        await run_command_async("pipx", "ensurepath")
    else:
        logger.error(f"Failed to install poetry via pipx. Return code: {result.returncode}")

    


async def main():
    logger.info("SAFE PC. Proxmox Post Install Script")
    #1. Remove the corporate repo and set to community
    logger.info("Removing corporate repo and setting to community")
    await remove_enterprise_repo()
    await remove_ceph_repo()
    await set_proxmox_repo_to_community()
    #2. Update and upgrade apt
    logger.info("Updating and upgrading apt")
    await update_and_upgrade_apt()
    #3. Install pipx via pip
    logger.info("Installing pipx via pip")
    await install_pipx_via_pip()
    #4. Install poetry via pipx
    logger.info("Installing poetry via pipx")
    await install_poetry_via_pipx()
    logger.info("Post install script completed successfully.")
    
    
    
    

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
    logger.info("Post install script finished execution.")