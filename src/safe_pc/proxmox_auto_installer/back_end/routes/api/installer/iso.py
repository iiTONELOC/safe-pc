import asyncio
import json
from logging import getLogger
from fastapi import Request
from passlib.hash import sha512_crypt
from fastapi.responses import JSONResponse

from safe_pc.proxmox_auto_installer.answer_file.answer_file import (
    ProxmoxAnswerFile,
    create_answer_file_from_dict,
)
from safe_pc.proxmox_auto_installer.back_end.iso_jobs import Job, below_max_jobs

LOGGER = getLogger("safe_pc.proxmox_auto_installer.routes.api.installer.iso")


async def check_max_jobs():
    if not await below_max_jobs():
        return JSONResponse(
            content={"error": "Maximum number of concurrent jobs reached."},
            status_code=429,
        )
    return None


async def post_installer_iso(request: Request) -> JSONResponse:

    try:
        # ensure we are below the max job limit
        resp = await check_max_jobs()
        if resp:
            return resp

        req_body = await request.body()
        data = json.loads(req_body)
        # JS doesn't have the sha512_crypt lib, so we hash it here - data is HTTPS so
        # Not, ideal but better than nothing - TIME permitting we should implement
        # the sha512_crypt in JS to match what linux uses, a regular digest won't work
        data["global"]["root-password-hashed"] = sha512_crypt.hash(
            data["global"]["root-password-hashed"]
        )
        LOGGER.info(
            f"Received ISO creation request with data: {json.dumps(data, indent=2)}"
        )
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
        return JSONResponse(
            {"status": "Created", "jobId": str(job.job_id)}, status_code=201
        )
    except Exception as _:
        LOGGER.error(f"Error processing ISO creation request: {_}")
        return JSONResponse(
            content={"error": f"Internal Server Error: {_}"}, status_code=500
        )
