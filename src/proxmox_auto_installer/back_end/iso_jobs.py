import json
import asyncio
from uuid import uuid4, UUID
from typing import Literal
from logging import getLogger

from fastapi import WebSocket

from proxmox_auto_installer.answer_file.cached_answers import CacheManager
from proxmox_auto_installer.iso.iso import ModifiedProxmoxISO, ProxmoxISO
from utm.utils.utils import calculate_percentage

MAX_JOBS = 5  # Maximum number of concurrent jobs
LOGGER = getLogger("proxmox_auto_installer.back_end.iso_jobs" if __name__ == "__main__" else __name__)


job_status = Literal["pending", "in_progress", "completed", "failed"]


class JobStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


from typing import Any


async def send_socket_update(ws: WebSocket, message: dict[str, Any]):
    """Send a JSON message over the websocket safely."""
    try:
        await ws.send_text(json.dumps(message))
    except Exception as e:
        LOGGER.error(f"Error sending socket update: {e}")


class Job:
    def __init__(self, info: str, job_id: UUID | None = None) -> None:
        self._lock = asyncio.Lock()
        self._stop_requested = False
        self._task: asyncio.Task[Any] | None = None
        self._socket: WebSocket | None = None
        self._proxmox_iso: ProxmoxISO | None = None
        self._modified_iso: ModifiedProxmoxISO | None = None
        self.info: str = info  # answer file as toml str
        self.install_progress: int = 0
        self.job_id: UUID = job_id or uuid4()
        self.status: job_status = JobStatus.PENDING
        self.cache = None

    async def update_status(self, new_status: job_status):
        async with self._lock:
            self.status = new_status

    async def update_progress(self, progress: int, message: str | None = None):
        async with self._lock:
            self.install_progress = progress
        if self._socket is not None:

            await send_socket_update(
                self._socket,
                {
                    "data": {
                        "type": "progress",
                        "progress": progress,
                        "status": self.status,
                        "message": message,
                    }
                },
            )

    async def attach_socket(self, ws: WebSocket):
        async with self._lock:
            self._socket = ws

    async def detach_socket(self):
        async with self._lock:
            self._socket = None

    async def to_json(self) -> dict[str, str | int]:
        async with self._lock:
            return {
                "job_id": str(self.job_id),
                "info": self.info,
                "status": self.status,
                "install_progress": self.install_progress,
            }

    async def run(self):
        self.cache = await CacheManager.new()
        await self.update_status(JobStatus.IN_PROGRESS)

        async with self._lock:
            LOGGER.info("Creating ProxmoxISO instance...")
            # create the prox iso instance if not already done
            self._proxmox_iso = await ProxmoxISO.new()

        # attempt to dl - skips if already done
        if not await self._proxmox_iso.download(
            on_update=lambda p, t, msg: asyncio.create_task(
                self.update_progress(
                    calculate_percentage(p, t),
                    msg or f"Downloading Proxmox ISO... {p}%",
                )
            )
        ):
            await self.on_finish(status=JobStatus.FAILED, progress=0)
            return

        # modify it
        await self.update_progress(calculate_percentage(4, 13), "Modifying Proxmox ISO...")
        LOGGER.info("Creating ModifiedProxmoxISO instance...")

        self._modified_iso = ModifiedProxmoxISO(self._proxmox_iso, str(self.job_id))
        try:
            modified_iso_path = await self._modified_iso.create_modified_iso(
                answer_file=self.info,
                on_update=lambda p, msg: asyncio.create_task(
                    self.update_progress(
                        calculate_percentage(p, 14),
                        msg or f"Modifying Proxmox ISO... {p}%",
                    )
                ),
            )
            # save the answer file to cache
            if modified_iso_path:
                await self.cache.put_answer_bytes(self.job_id.__str__(), self.info.encode())

            LOGGER.info(f"Modified ISO path: {modified_iso_path}")
        except Exception as e:
            LOGGER.exception(f"Error during ISO modification: {e}")
            modified_iso_path = None

        if not modified_iso_path:
            await self.on_finish(status=JobStatus.FAILED, progress=0)
            return

        await self.update_progress(100, "Job completed successfully.")

        await self.on_finish()

    async def start(self):
        LOGGER.info(f"Starting job {self.job_id}...")
        await add_job(self)
        self._task = asyncio.create_task(self.run())
        await asyncio.sleep(0.3)  # allow task to start

    async def stop(self, status: job_status = JobStatus.COMPLETED, progress: int = 100):
        LOGGER.info(f"Stopping job {self.job_id}...")
        self._stop_requested = True
        await self.on_finish(status=status, progress=progress)

    async def on_finish(self, status: job_status = JobStatus.COMPLETED, progress: int = 100):
        await self.update_status(status)
        await self.update_progress(progress)

        if status == JobStatus.COMPLETED and self._modified_iso:
            try:
                # /.../data/isos  (NOT parent.parent)
                isos_root = self._modified_iso.base_iso.iso_dir.parent  # type: ignore
                final_path = self._modified_iso.move_iso_to_final_location(final_dir=isos_root)  # type: ignore
                if self.cache:
                    await self.cache.set_iso_path(self.job_id.__str__(), final_path)  # STORE FILE PATH
            except Exception as e:
                LOGGER.error(f"Error moving ISO to final location: {e}")
                await self.update_status(JobStatus.FAILED)
                await self.update_progress(0)

        await remove_job(str(self.job_id))
        if self._socket:
            try:
                await self._socket.close()
            except Exception as e:
                LOGGER.error(f"Error closing socket: {e}")
            self._socket = None
        if self._task:
            self._task.cancel()
            self._task = None


# Registry
_lock = asyncio.Lock()
_jobs: dict[str, Job] = {}


async def add_job(job: Job):
    async with _lock:
        _jobs[str(job.job_id)] = job


async def remove_job(job_id: str):
    async with _lock:
        _jobs.pop(job_id, None)


async def get_job(job_id: str) -> Job | None:
    async with _lock:
        return _jobs.get(job_id)


async def count_jobs() -> int:
    async with _lock:
        return len(_jobs)


async def below_max_jobs() -> bool:
    async with _lock:
        return len(_jobs) < MAX_JOBS
