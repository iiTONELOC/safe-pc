from logging import Logger
from utm.utils.utils import pexpect_connect_to_serial_socket  # type: ignore
from utm.proxmox.vms import stop_vm, get_vm_status, get_vm_serial_socket_path, vm_start_if_not_running


class ConsoleDriver:
    def __init__(self, vm_id: int, logger: Logger, prefix: str, stop_on_exit: bool = False) -> None:
        self.vm_id = vm_id
        self.logger = logger
        self.prefix = prefix
        self.child = None  # type: ignore
        self.stop_on_exit = stop_on_exit

    async def __aenter__(self) -> "ConsoleDriver":
        try:
            await vm_start_if_not_running(str(self.vm_id))
            self.child = pexpect_connect_to_serial_socket(  # type: ignore
                get_vm_serial_socket_path(str(self.vm_id)), self.logger, prefix=self.prefix
            )
        except Exception as e:
            self.logger.error(f"{self.prefix} Failed to start VM {self.vm_id}: {e}")
            raise

        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore

        # ensure the socket is closed
        if self.child:  # type: ignore
            self.child.close(force=True)  # type: ignore

        if self.stop_on_exit:
            try:
                status = await get_vm_status(str(self.vm_id))
                if "status: running" in status:
                    await stop_vm(str(self.vm_id))
            except Exception as e:
                self.logger.error(f"{self.prefix} Failed to stop VM {self.vm_id}: {e}")
                raise
