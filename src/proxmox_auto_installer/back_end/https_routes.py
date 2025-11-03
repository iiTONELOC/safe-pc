from typing import Any
from datetime import datetime
from logging import getLogger
from json import loads as json_loads

from utm.utils.utils import get_local_ip
from proxmox_auto_installer.back_end.helpers import DevHelpers
from proxmox_auto_installer.utils.tzd import ProxmoxTimezoneHelper
from proxmox_auto_installer.constants import PROXMOX_ALLOWED_KEYBOARDS
from proxmox_auto_installer.back_end.iso_jobs import Job, below_max_jobs
from proxmox_auto_installer.answer_file.cached_answers import CacheManager
from proxmox_auto_installer.utils.country_codes import ProxmoxCountryCodeHelper
from proxmox_auto_installer.back_end.iso_jobs import get_job, send_socket_update
from proxmox_auto_installer.answer_file.cached_answers import CacheManager
from proxmox_auto_installer.answer_file.answer_file import (
    ProxmoxAnswerFile,
    NETWORK_CONFIG_DEFAULTS,
    create_answer_file_from_dict,
)

from passlib.hash import sha512_crypt
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect

LOGGER = getLogger(__name__)


async def check_max_jobs():
    if not await below_max_jobs():
        return JSONResponse(
            content={"error": "Maximum number of concurrent jobs reached."},
            status_code=429,
        )
    return None


class HttpsRoutes:
    START_YEAR = 2025  # Project start year for copyright
    CSP_POLICY = (
        "default-src 'self'; "
        f"connect-src 'self' wss://{get_local_ip()}:33008; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
    )
    CURRENT_YEAR = datetime.now().year  # Current year for copyright

    @staticmethod
    def register(
        app: FastAPI,
        templates: Jinja2Templates,
        dev: bool = False,
    ) -> None:
        """
        Registers the routes for the Proxmox Installer application.

        Args:
            app (FastAPI): The FastAPI application instance to which the routes will be added.
            templates (Jinja2Templates): The Jinja2Templates instance used for rendering templates.
            dev (bool, optional): If True, enables development mode features. Defaults to False.
        """

        # Middleware to add Content-Security-Policy headers, ensures this is attached first
        @app.middleware(middleware_type="http")
        async def csp_middleware(request: Request, call_next: Any) -> HTMLResponse:  # type: ignore
            response: HTMLResponse = await call_next(request)
            response.headers["Content-Security-Policy"] = HttpsRoutes.CSP_POLICY
            return response

        # Root endpoint serving the main page
        @app.get(path="/", response_class=HTMLResponse)
        async def read_root(request: Request):  # type: ignore
            # generate a new jwt for the session if needed

            response = templates.TemplateResponse(
                name="/pages/main.html",
                context={
                    "request": request,
                    "start_year": HttpsRoutes.START_YEAR,
                    "current_year": HttpsRoutes.CURRENT_YEAR,
                    "SAFE_CIDR": NETWORK_CONFIG_DEFAULTS["cidr"],
                    "SAFE_GATEWAY": NETWORK_CONFIG_DEFAULTS["gateway"],
                    "SAFE_DNS": NETWORK_CONFIG_DEFAULTS["dns"],
                },
            )

            return response

        # history
        @app.get(path="/history", response_class=HTMLResponse)
        async def history_page(request: Request):  # type: ignore
            # generate a new jwt for the session if needed
            cached_manager = await CacheManager.new()
            job_ids = await cached_manager.get_cached_job_ids()
            response = templates.TemplateResponse(
                name="/pages/history.html",
                context={
                    "request": request,
                    "job_ids": job_ids,
                    "start_year": HttpsRoutes.START_YEAR,
                    "current_year": HttpsRoutes.CURRENT_YEAR,
                },
            )

            return response

        # history-detail
        @app.get(path="/history/{job_id}", response_class=HTMLResponse)
        async def history_detail_page(request: Request, job_id: str):  # type:ignore
            # generate a new jwt for the session if needed

            cached_manager = await CacheManager.new()
            ans_path = cached_manager.get_answer_path(job_id=job_id)
            if not ans_path:
                return templates.TemplateResponse(
                    name="/pages/404.html",
                    context={
                        "request": request,
                        "start_year": HttpsRoutes.START_YEAR,
                        "current_year": HttpsRoutes.CURRENT_YEAR,
                    },
                    status_code=404,
                )

            response = templates.TemplateResponse(
                name="/pages/history-detail.html",
                context={
                    "request": request,
                    "start_year": HttpsRoutes.START_YEAR,
                    "current_year": HttpsRoutes.CURRENT_YEAR,
                    "job_id": job_id,
                },
            )

            return response

        @app.get(path="/iso-download/{job_id}", response_class=HTMLResponse)
        async def iso_download_page(request: Request, job_id: str):  # type: ignore
            # generate a new jwt for the session if needed

            cached_manager = await CacheManager.new()
            iso_path = cached_manager.get_iso_path(job_id=job_id)
            if not iso_path:
                return templates.TemplateResponse(
                    name="/pages/404.html",
                    context={
                        "request": request,
                        "start_year": HttpsRoutes.START_YEAR,
                        "current_year": HttpsRoutes.CURRENT_YEAR,
                    },
                    status_code=404,
                )

            response = templates.TemplateResponse(
                name="/pages/iso-download.html",
                context={
                    "request": request,
                    "start_year": HttpsRoutes.START_YEAR,
                    "current_year": HttpsRoutes.CURRENT_YEAR,
                    "job_id": job_id,
                },
            )

            return response

        # Development mode features - hot-reloading, etc.

        DevHelpers.handle_dev_hot_reload(app=app, templates=templates)  # type: ignore

        # answer-file dl page
        @app.get(path="/api/answer-file/{job_id}", response_class=FileResponse)
        async def answer_file_page(request: Request, job_id: str):  # type: ignore
            cached_manager = await CacheManager.new()
            answer_path = cached_manager.get_answer_path(job_id=job_id)
            if not answer_path:
                return JSONResponse(content={"error": "Answer file not found."}, status_code=404)
            return FileResponse(
                path=answer_path,
                filename=f"{job_id}-answer_file.toml",
                media_type="text/plain",
            )

        @app.get(path="/api/installer/data", response_class=JSONResponse)
        def get_installer_data_route() -> dict[str, dict[str, Any]]:  # type: ignore
            """Get the data required for the installer settings page."""
            tz_helper = ProxmoxTimezoneHelper()
            cc_helper = ProxmoxCountryCodeHelper()
            # need to grab some data for the front end
            # we need our timezones, keyboard layouts, and list of countries

            key_layouts = PROXMOX_ALLOWED_KEYBOARDS
            tsz = tz_helper.get_timezones()
            ccd = cc_helper.get_country_codes()
            current_tz = tz_helper.get_local_timezone()
            current_country = tz_helper.get_local_country_code()
            return {
                "installerSettings": {
                    "timezones": tsz,
                    "keyboards": key_layouts,
                    "countries": ccd,
                    "currentTimezone": current_tz,
                    "currentCountry": current_country,
                }
            }

        @app.post(path="/api/installer/iso", response_class=JSONResponse)
        async def installer_iso_route(request: Request):  # type: ignore
            try:
                # ensure we are below the max job limit
                resp = await check_max_jobs()
                if resp:
                    return resp

                req_body = await request.body()
                data = json_loads(req_body)
                # JS doesn't have the sha512_crypt lib, so we hash it here - data is HTTPS so
                # Not, ideal but better than nothing - TIME permitting we should implement
                # the sha512_crypt in JS to match what linux uses, a regular digest won't work
                data["global"]["root-password-hashed"] = sha512_crypt.hash(data["global"]["root-password-hashed"])
                LOGGER.info("Received ISO creation request")
                answer_file: ProxmoxAnswerFile = create_answer_file_from_dict(data)

                resp = await check_max_jobs()
                if resp:
                    return resp

                # Create a new job for ISO creation
                job = Job(info=answer_file.to_toml_str())
                LOGGER.info(f"Created job with ID: {job.job_id}, starting ISO creation...")
                # Start the ISO creation job in a new thread
                await job.start()

                # send the job id back to the client
                return JSONResponse({"status": "Created", "jobId": str(job.job_id)}, status_code=201)
            except Exception as _:
                LOGGER.error(f"Error processing ISO creation request: {_}")
                return JSONResponse(content={"error": f"Internal Server Error: {_}"}, status_code=500)

        # iso-download route
        @app.get(path="/api/iso-download/{job_id}")
        async def iso_download_route(request: Request, job_id: str):  # type: ignore
            LOGGER.info(f"Received ISO download request for job ID: {job_id}")
            try:
                cache = await CacheManager.new()
                iso_path = cache.get_iso_path(job_id)
                short_id = job_id.split("-")[-1][:8]  # last chunk, first 8 chars
                filename = f"SAFE-PC-{short_id}.iso"
                if not iso_path:
                    raise FileNotFoundError("ISO not found for the given job ID.")
                return FileResponse(
                    path=iso_path,
                    filename=filename,
                    media_type="application/octet-stream",
                )
            except Exception as _:
                LOGGER.error(f"Error processing ISO download request: {_}")
                return JSONResponse(content={"error": f"Internal Server Error: {_}"}, status_code=500)

        # delete-iso route
        @app.delete(path="/api/delete-iso/{job_id}")
        async def delete_iso_route(request: Request, job_id: str):  # type: ignore
            try:
                LOGGER.info(f"Received request to delete ISO and answer file for job ID: {job_id}")
                cache = await CacheManager.new()
                await cache.delete_answer(job_id)
                LOGGER.info(f"Deleted answer file for job ID: {job_id}")
                await cache.delete_iso(job_id, remove_file=True)
                LOGGER.info(f"Deleted ISO for job ID: {job_id}")
                return JSONResponse(content={"status": "ISO and answer file deleted successfully."}, status_code=200)
            except Exception as _:
                LOGGER.error(f"Error processing ISO delete request: {_}")
                return JSONResponse(content={"error": f"Internal Server Error: {_}"}, status_code=500)

        # websocket route for job status updates
        @app.websocket("/api/ws/iso")
        async def installer_iso_ws_route(websocket: WebSocket):  # type: ignore

            await websocket.accept()
            data = await websocket.receive_text()
            msg = json_loads(data)
            job_id = msg.get("jobId", None)
            LOGGER.info(f"WebSocket connection request for job {job_id}")
            job = await get_job(job_id)
            LOGGER.info(f"Found job: {job}")
            if not job or job._socket is not None:  # type: ignore
                await websocket.close(code=1008)
                return
            LOGGER.info(f"Attaching socket to job {job_id}")
            await job.attach_socket(websocket)
            LOGGER.info(f"Job {job_id} status: {job.status}, progress: {job.install_progress}")
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

        @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
        async def catch_all(request: Request, full_path: str):  # type: ignore
            return templates.TemplateResponse(
                "pages/404.html",
                {
                    "request": request,
                    "start_year": HttpsRoutes.START_YEAR,
                    "current_year": HttpsRoutes.CURRENT_YEAR,
                },
                status_code=404,
            )
