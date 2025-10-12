import json
from logging import getLogger
from safe_pc.proxmox_auto_installer.back_end.iso_jobs import get_job, send_socket_update
from safe_pc.proxmox_auto_installer.back_end.routes.api.installer import (
    get_installer_data,
    post_installer_iso,
)
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect

LOGGER = getLogger("safe_pc.proxmox_auto_installer.routes.api")


class APIRoutes:

    @staticmethod
    def register(
        app: FastAPI,
        templates: Jinja2Templates,
        dev: bool = False,
    ):
        # return a 200 hello work json response for testing
        @app.get(path="/api/installer/data")
        def get_installer_data_route():# type: ignore
            return get_installer_data()# type: ignore

        @app.post(path="/api/installer/iso")
        async def installer_iso_route(request: Request):# type: ignore
            return await post_installer_iso(request)

        # websocket route for job status updates
        @app.websocket("/api/ws/iso")
        async def installer_iso_ws_route(websocket: WebSocket):# type: ignore

            await websocket.accept()
            data = await websocket.receive_text()
            msg = json.loads(data)
            job_id = msg.get("jobId", None)
            LOGGER.info(f"WebSocket connection request for job {job_id}")
            job = await get_job(job_id)
            LOGGER.info(f"Found job: {job}")
            if not job or job._socket is not None: # type: ignore
                await websocket.close(code=1008)
                return
            LOGGER.info(f"Attaching socket to job {job_id}")
            await job.attach_socket(websocket)
            LOGGER.info(
                f"Job {job_id} status: {job.status}, progress: {job.install_progress}"
            )
            await send_socket_update(
                websocket,
                {
                    "data": {
                        "type": "progress",
                        "progress": job.install_progress,
                        "status": job.status,
                        "message": f"Job {job.job_id} reattached or initialized",
                    }
                },
            )

            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                LOGGER.info(f"WebSocket disconnected for job {job_id}")
                await job.detach_socket()
        