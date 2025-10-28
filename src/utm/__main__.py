#!/usr/bin/python3.13
import os
import asyncio
from sys import argv
from pathlib import Path
from re import search, sub, M, compile
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from logging.handlers import RotatingFileHandler
from logging import INFO, WARNING, Logger, Formatter, StreamHandler, DEBUG, getLogger


logger = getLogger("safe_pc.post_startup")

CWD = "/opt/safe_pc"
BACKUP_LOG_COUNT = 5  # in days
ENV_P = Path("/etc/environment")
BASH_RC = Path("/etc/bash.bashrc")
SCRIPT_PATH = Path(argv[0]).resolve()


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


def set_env_variable(key: str, value: str, system_wide: bool = True):
    env_path = Path(ENV_P)
    bashrc_path = Path(BASH_RC)
    env_path.touch(exist_ok=True)
    bashrc_path.touch(exist_ok=True)

    def update_file(path: Path, pattern: str, new_line: str):
        content = path.read_text()
        if search(pattern, content, flags=M):
            updated = sub(pattern, new_line, content, flags=M)
            if updated != content:
                path.write_text(updated)
        else:
            with path.open("a") as f:
                f.write(f"\n{new_line}\n")

    if system_wide:
        env_line = f'{key}="{value}"'
        env_pattern = rf"^{key}=.*$"
        update_file(env_path, env_pattern, env_line)

    # Update bashrc
    bash_line = f'export {key}="{value}"'
    bash_pattern = rf"^export {key}=.*$"
    update_file(bashrc_path, bash_pattern, bash_line)

    # Set in current environment if not already set
    if os.getenv(key, "") != value:
        os.environ[key] = value


def remove_env_variable(key: str, system_wide: bool = True):
    env_path = Path(ENV_P)
    bashrc_path = Path(BASH_RC)

    def remove_from_file(path: Path, pattern: str):
        content = path.read_text()
        updated = sub(pattern, "", content, flags=M)
        if updated != content:
            path.write_text(updated)

    if system_wide:
        env_pattern = rf"^{key}=.*$\n?"
        remove_from_file(env_path, env_pattern)

    # Remove from bashrc
    bash_pattern = rf"^export {key}=.*$\n?"
    remove_from_file(bashrc_path, bash_pattern)

    # Remove from current environment
    if key in os.environ:
        del os.environ[key]


def _project_log_dir() -> Path:
    """Get the project's log directory, creating it if necessary."""
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _project_log_file() -> Path:
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


LOG_LINE_PATTERN = compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} - \[")


async def stream_output(
    stream: asyncio.StreamReader,
    lines: list[str],
    level: int,
    logger: Logger,
) -> None:
    while True:
        line = await stream.readline()
        if not line:
            break
        text = line.decode(errors="replace").rstrip()
        lines.append(text)
        if not text.strip():
            continue

        # Detect already-prefixed log lines and print accordingly
        if level == INFO:
            logger.log(level, text)
        elif level == WARNING and LOG_LINE_PATTERN.match(text):
            print(text, flush=True)
        else:
            logger.log(level, text)


async def run_command_async(
    *args: str | Path,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    logger: Logger | None = None,
) -> CmdResult:
    cmd = tuple(str(a) for a in args)

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    if logger is None:
        logger = getLogger("safe_pc.run_command_async")
        logger.propagate = False

    await asyncio.gather(
        stream_output(proc.stdout, stdout_lines, INFO, logger),  # type: ignore
        stream_output(proc.stderr, stderr_lines, WARNING, logger),  # type: ignore
    )

    rc = await proc.wait()
    stdout = "\n".join(stdout_lines)
    stderr = "\n".join(stderr_lines)

    if check and rc != 0:
        raise CommandError(cmd, rc, stdout, stderr)

    return CmdResult(stdout, stderr, rc)


# End Reusable Exports ------

# ------------------------------------------------------------------------------

# Post Startup --------------


async def is_proxmox() -> bool:
    cmd = "pveversion"
    result = await run_command_async(cmd, cwd=CWD, check=False)
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
            logger.info("Removing enterprise repository file")
            repo_file.unlink()
            logger.info(f"  Removed enterprise repository file: {repo_file}")
        else:
            logger.info("  Enterprise repository file not found, skipping removal.")
    except Exception as e:
        logger.error(f"  Failed to remove enterprise repository file: {e}")


def remove_ceph_repo():
    repo_file = Path("/etc/apt/sources.list.d/ceph.sources")
    try:

        if repo_file.exists():
            logger.info("Removing Ceph repository file")
            repo_file.unlink()
            logger.info(f"  Removed Ceph repository file: {repo_file}")
        else:
            logger.info(f"  No Ceph repository file found at: {repo_file}")
    except Exception as e:
        logger.error(f"  Failed to remove Ceph repository file: {e}")


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
    logger.info("Setting Proxmox repository to community edition")
    try:
        # Write the new repository configuration
        with open(repo_file, mode="w") as f:
            f.write(repo_str.strip() + "\n")
            logger.info(f"  Set Proxmox repository to community edition in {repo_file}")

    except Exception as e:
        logger.error(f"  Failed to set Proxmox repository: {e}")


async def update_and_upgrade_apt():

    env = {"DEBIAN_FRONTEND": "noninteractive"}
    try:
        logger.info("Updating and upgrading apt repositories...")
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
        logger.info("  Successfully updated and upgraded apt repositories.")
    except CommandError as e:
        logger.error(f"  APT update/upgrade failed: {e}")


def set_production_env():
    # Check current in-memory environment first
    if os.getenv("CAPSTONE_PRODUCTION", "0") == "1":
        logger.info("CAPSTONE_PRODUCTION is already set to '1' in current environment. Skipping.")
        return

    set_env_variable("CAPSTONE_PRODUCTION", "1", system_wide=True)


async def dl_opnsense_iso():
    await run_command_async(
        "venv/bin/python3",
        "src/utm/opnsense/opnsense.py",
        cwd=CWD,
        env=os.environ,
    )


async def install_pythonvenv():
    logger.info("Checking for python3-venv installation...")
    result_check = await run_command_async("which", "python3", "-m", "venv", check=False)
    if result_check.returncode == 0:
        logger.info("  python3-venv is already installed, skipping installation.")
        return
    logger.info("  Installing python3-venv...")
    result = await run_command_async("apt", "install", "-y", "python3-venv", check=False)

    if result.returncode == 0:
        logger.info("  Installed python3-venv successfully.")
    else:
        raise ValueError(f"  Failed to install python3-venv. Return code: {result.returncode}")


async def create_venv():
    venv_path = Path(CWD) / "venv"
    if venv_path.exists():
        logger.info("Python virtual environment already exists, skipping creation.")
        return

    logger.info("Creating Python virtual environment...")
    result = await run_command_async("python3", "-m", "venv", str(venv_path), check=False)

    if result.returncode == 0:
        logger.info("  Created Python virtual environment successfully.")
    else:
        raise ValueError(f"  Failed to create Python virtual environment. Return code: {result.returncode}")


async def install_requirements():
    logger.info("Installing Python requirements in virtual environment...")
    venv_path = Path(CWD) / "venv"
    pip_path = venv_path / "bin" / "pip"
    requirements_file = Path(CWD) / "requirements.txt"

    if not requirements_file.exists():
        logger.error(f"  Requirements file not found at {requirements_file}.")
        return

    result = await run_command_async(str(pip_path), "install", "-r", str(requirements_file), check=False)

    if result.returncode == 0:
        logger.info("  Installed Python requirements successfully.")
    else:
        raise ValueError(f"  Failed to install Python requirements. Return code: {result.returncode}")


async def install_safe_pc_via_pip():
    # install -e so modules imports work correctly

    logger.info("Installing SAFE PC via pip in virtual environment...")
    venv_path = Path(CWD) / "venv"
    pip_path = venv_path / "bin" / "pip"
    result = await run_command_async(str(pip_path), "install", "-e", CWD, check=False)
    if result.returncode == 0:
        logger.info("  Successfully installed SAFE PC via pip in virtual environment.")
    else:
        err_msg = f"Failed to install SAFE PC via pip in virtual environment. Return code: {result.returncode}"
        logger.error(err_msg)
        raise ValueError(err_msg)


async def setup_venv_reqs_and_install_safe_pc():
    await install_pythonvenv()
    await create_venv()
    await install_requirements()
    await install_safe_pc_via_pip()


async def create_vm_data_pool_if_missing():
    # use rpool/vm-data
    result: CmdResult = await run_command_async(
        *[
            "zfs",
            "list",
            "rpool/vm-data",
        ],
        check=False,
    )

    if result.returncode != 0:
        logger.info("Creating ZFS dataset rpool/vm-data for VM storage...")
        result_create: CmdResult = await run_command_async(
            *[
                "zfs",
                "create",
                "-o",
                "mountpoint=none",
                "rpool/vm-data",
            ],
            check=False,
        )
        if result_create.returncode != 0:
            logger.error(f"Failed to create ZFS dataset rpool/vm-data: {result_create.stderr}")
        else:
            logger.info("Successfully created ZFS dataset rpool/vm-data.")
            # register dataset with Proxmox
            await run_command_async(
                *[
                    "pvesm",
                    "add",
                    "zfspool",
                    "zfs-vm-data",
                    "--pool",
                    "rpool/vm-data",
                    "--content",
                    "images,rootdir",
                    "--sparse",
                    "1",
                ],
                check=False,
            )


async def create_opnsense_vm():
    logger.info("Creating OPNsense VM...")
    await run_command_async(
        "venv/bin/python3",
        "src/utm/opnsense/vm_creator.py",
        cwd=CWD,
        check=False,
        env=os.environ,
        logger=logger,
    )


# group and loop
post_startup_steps = (
    (set_production_env, "Setting production environment variable"),
    (remove_enterprise_repo, "Removing corporate repo"),
    (remove_ceph_repo, "Removing Ceph repo"),
    (set_proxmox_repo_to_community, "Setting Proxmox repo to community"),
    (update_and_upgrade_apt, "Updating and upgrading apt"),
    (setup_venv_reqs_and_install_safe_pc, "Setting up venv, installing requirements, and installing SAFE PC via pip"),
    (dl_opnsense_iso, "Checking for OPNsense ISO"),
    (create_vm_data_pool_if_missing, "Creating VM data pool if missing"),
    (create_opnsense_vm, "Checking for OPNsense VM"),
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

    logger.info("SAFE PC Loaded Successfully - Proxmox Post Startup Script Complete")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
    exit(0)
