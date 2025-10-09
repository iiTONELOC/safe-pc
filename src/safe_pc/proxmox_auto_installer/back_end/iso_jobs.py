import json
import asyncio
from uuid import uuid4
from typing import Literal
from threading import Lock
from logging import getLogger

from fastapi import WebSocket

MAX_JOBS = 5  # Maximum number of concurrent jobs
LOGGER = getLogger(
    "safe_pc.proxmox_auto_installer.back_end.iso_jobs"
    if __name__ == "__main__"
    else __name__
)
job_status = Literal["pending", "in_progress", "completed", "failed"]


class JobStatus:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


async def send_socket_update(ws: WebSocket, message: dict):
    """Send a JSON message over the websocket safely."""
    try:
        await ws.send_text(json.dumps(message))
    except Exception as e:
        LOGGER.error(f"Error sending socket update: {e}")


class Job:
    def __init__(self, info: dict[str, str], job_id: uuid4 = None) -> None:
        self._lock = Lock()
        self._stop_requested = False
        self._socket: WebSocket | None = None
        self.info: dict[str, str] = info
        self.install_progress: int = 0
        self.job_id: uuid4 = job_id or uuid4()
        self.status: job_status = JobStatus.PENDING
        self._task: asyncio.Task | None = None

    def update_status(self, new_status: job_status):
        with self._lock:
            self.status = new_status

    async def update_progress(self, progress: int):
        with self._lock:
            self.install_progress = progress
        if self._socket is not None:
            await send_socket_update(
                self._socket,
                {
                    "data": {
                        "type": "progress",
                        "progress": progress,
                        "status": self.status,
                    }
                },
            )

    def attach_socket(self, ws: WebSocket):
        with self._lock:
            self._socket = ws

    def detach_socket(self):
        with self._lock:
            self._socket = None

    def to_json(self):
        with self._lock:
            return {
                "job_id": str(self.job_id),
                "info": self.info,
                "status": self.status,
                "install_progress": self.install_progress,
            }

    async def run(self):
        LOGGER.info(f"Running job {self.job_id}...")
        self.update_status(JobStatus.IN_PROGRESS)
        while not self._stop_requested:
            await asyncio.sleep(1)
            await self.update_progress(self.install_progress + 10)
            if self.install_progress >= 100:
                break
        await self.on_finish()

    def start(self):
        LOGGER.info(f"Starting job {self.job_id}...")
        add_job(self)
        self._task = asyncio.create_task(self.run())

    async def stop(self, status: job_status = JobStatus.COMPLETED, progress: int = 100):
        LOGGER.info(f"Stopping job {self.job_id}...")
        self._stop_requested = True
        await self.on_finish(status=status, progress=progress)

    async def on_finish(
        self, status: job_status = JobStatus.COMPLETED, progress: int = 100
    ):
        self.update_status(status)
        await self.update_progress(progress)
        remove_job(str(self.job_id))
        if self._socket:
            try:
                await self._socket.close()
            except Exception as e:
                LOGGER.error(f"Error closing socket: {e}")
            self._socket = None


# Registry
_lock = Lock()
_jobs: dict[str, Job] = {}


def add_job(job: Job):
    with _lock:
        _jobs[str(job.job_id)] = job


def remove_job(job_id: str):
    with _lock:
        _jobs.pop(job_id, None)


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _jobs.get(job_id)


def count_jobs() -> int:
    with _lock:
        return len(_jobs)


def below_max_jobs() -> bool:
    with _lock:
        return len(_jobs) < MAX_JOBS
