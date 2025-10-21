#!/usr/bin/python3.13
"""
Dependency-Free Proxmox Post Startup Script for SAFE PC.

The script performs the following tasks:
    1. Checks if running on Proxmox.
    2. Removes enterprise and Ceph repositories.
    3. Sets Proxmox repository to community edition.
    4. Updates and upgrades apt repositories.
    5. Installs pipx if not already installed.
    6. Installs poetry via pipx if not already installed.
    7. Sets the CAPSTONE_PRODUCTION environment variable.
    8. Installs SAFE PC using poetry.
    9. Downloads the OPNsense ISO.

Logs @ /opt/capstone/safe_pc/logs/safe_pc.log
"""
import os
import asyncio
from sys import argv
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from logging.handlers import RotatingFileHandler
from logging import INFO, Logger, Formatter, StreamHandler, DEBUG, getLogger

logger = getLogger("safe_pc.post_startup")

BACKUP_LOG_COUNT = 5  # in days
BASH_RC = Path("/etc/bash.bashrc")
SCRIPT_PATH = Path(argv[0]).resolve()
PROJECT_ROOT = SCRIPT_PATH.parent.parent
POETRY_PATH = "/root/.local/share/pipx/venvs/poetry/bin/poetry"


# Reusable Exports - Moved here to prevent circular imports - Clearly should go elsewhere
def is_testing() -> bool:
    """Check if the code is running in a testing environment.

    Returns:
        bool: True if running tests, False otherwise.
    """
    return os.getenv("CAPSTONE_TESTING", "0") == "1"


def is_production() -> bool:
    """Check if the code is running in a production environment.

    Returns:
        bool: True if running in production, False otherwise.
    """
    return os.getenv("CAPSTONE_PRODUCTION", "0") == "1"


def is_verbose() -> bool:
    """Check if verbose mode is enabled via command-line arguments.

    Returns:
        bool: True if verbose mode is enabled, False otherwise.
    """
    return os.getenv("CAPSTONE_VERBOSE", "0") == "1"


def _project_log_dir() -> Path:
    """Get the project's log directory, creating it if necessary."""
    log_dir = Path(__file__).resolve().parents[3] / "logs"
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _project_log_file():
    """Get the project's log file path."""
    log_file = "safe_pc_tests" if is_testing() else "safe_pc"
    log_dir = _project_log_dir()
    log_path = log_dir / f"{log_file}.log"
    return log_path


def setup_logging(level: int = INFO, log_file: str = "safe_pc") -> Logger:
    """
    Configure root logging once for the entire process.
    Returns the package logger for convenience.

    Args:
        level: The level to set, i.e. INFO, DEBUG, ERROR, etc.

    Returns:
        The configured root-level logger
    """

    # determine if we need DEBUG level logging
    if level != DEBUG and is_testing() or is_verbose():
        level = DEBUG

    log_path = _project_log_file()
    fmt = Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")

    file_handler = RotatingFileHandler(
        log_path,
        mode="a" if not is_testing() else "w",
        backupCount=BACKUP_LOG_COUNT,
    )
    file_handler.setFormatter(fmt)

    # Console handler
    stream_handler = StreamHandler()
    stream_handler.setFormatter(fmt)

    # config logger
    root = getLogger()
    root.handlers.clear()
    root.name = log_file
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)

    return getLogger(log_file)


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


# End Reusable Exports ------

# ------------------------------------------------------------------------------

# Post Startup --------------


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
        with open(repo_file, mode="w") as f:
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
    result_check = await run_command_async("which", "pipx", check=False)
    if result_check.returncode == 0:
        logger.info("pipx is already installed, skipping installation.")
        return
    result = await run_command_async("apt", "install", "-y", "pipx")
    if result.returncode == 0:
        logger.info("Successfully installed pipx.")
    else:
        raise ValueError(f"Failed to install pipx. Return code: {result.returncode}")


async def install_poetry_via_pipx():
    result_check = await run_command_async("which", "poetry", check=False)
    if result_check.returncode == 0:
        logger.info("Poetry is already installed, skipping installation.")
        return
    result = await run_command_async("pipx", "install", "poetry")
    if result.returncode != 0:
        logger.error(f"Failed to install poetry via pipx. Return code: {result.returncode}")
        return

    logger.info("Successfully installed poetry via pipx.")
    await run_command_async("pipx", "ensurepath")

    poetry_bin = os.path.expanduser("~/.local/share/pipx/venvs/poetry/bin")
    path_line = f'PATH="{poetry_bin}:$PATH"'

    with open(BASH_RC, mode="a") as f:  # NOSONAR
        f.write(f"\nexport {path_line}\n")

    logger.info("Poetry installation and path setup complete.")


def set_production_env():

    # check if CAPSTONE_PRODUCTION is already set
    if os.getenv("CAPSTONE_PRODUCTION", "0") == "1":
        logger.info("CAPSTONE_PRODUCTION is already set to '1'. Skipping.")
        return

    path_line = '\nexport CAPSTONE_PRODUCTION="1"\n'
    with open(BASH_RC, mode="a") as f:
        f.write(path_line)

        logger.info("Set CAPSTONE_PRODUCTION environment variable to '1' for production mode.")


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


# group and loop
post_startup_steps = (
    (set_production_env, "Setting production environment variable"),
    (remove_enterprise_repo, "Removing corporate repo"),
    (remove_ceph_repo, "Removing Ceph repo"),
    (set_proxmox_repo_to_community, "Setting Proxmox repo to community"),
    (update_and_upgrade_apt, "Updating and upgrading apt"),
    (install_pipx, "Installing pipx"),
    (install_poetry_via_pipx, "Installing poetry via pipx"),
    (install_safe_pc, "Installing SAFE PC via poetry"),
    (dl_opnsense_iso, "Downloading OPNsense ISO"),
)


@only_on_proxmox
async def main():
    setup_logging()  # ensures the logger is configured - poetry calls the main function directly
    logger.info("SAFE PC. Executing Proxmox Post Startup Script")

    for step in post_startup_steps:
        func, description = step
        logger.debug(f"Starting step: {description}")
        try:
            await func() if asyncio.iscoroutinefunction(func) else func()
            logger.debug(f"Completed step: {description}")
        except Exception as e:
            logger.error(f"Error during step '{description}': {e}")
            logger.info("Aborting post installation due to error.")
            exit(1)

    logger.info("SAFE PC Loaded Successfully")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
    exit(0)
