# import sys
# import time
from logging import Logger, getLogger, INFO
import pexpect

logger = getLogger("utm.opnsense.install_and_configure")

base_prefix = "[OPNSense Install] "
logout_time_mins = 10
logout_time_secs = logout_time_mins * 60


class PexpectLogger:
    def __init__(self, logger: Logger, level: int = INFO, prefix: str = ""):
        self.logger = logger
        self.level = level
        self.prefix = prefix

    def write(self, message: str):
        message = message.strip()
        if message:
            self.logger.log(self.level, f"{self.prefix}{message}")

    def flush(self):
        pass


def install_and_configure_opnsense(vm_id: str, root_password: str):

    # connect to OPNsense via the console - SSH isn't supported until after initial setup
    child = pexpect.spawn(f"qm terminal {vm_id}", encoding="utf-8", timeout=logout_time_secs)  # type: ignore
    child.logfile_read = PexpectLogger(logger, prefix=base_prefix + "[VM Output] ")
    child.logfile_send = PexpectLogger(logger, prefix=base_prefix + "[VM Input] ")

    try:
        # wait for the initial OPNsense prompt
        child.expect("Press Enter to continue")
        child.sendline("")

        # wait for the login prompt
        child.expect("login:")

        # send installer login
        child.sendline("installer")
        child.expect("Password:")
        child.sendline("opnsense")

        # navigate the installer menus
    except pexpect.exceptions.TIMEOUT:
        logger.error(f"{base_prefix}Timeout occurred during installation.")
    except pexpect.exceptions.EOF:
        logger.error(f"{base_prefix}Unexpected EOF from VM console.")
    finally:
        child.close()
