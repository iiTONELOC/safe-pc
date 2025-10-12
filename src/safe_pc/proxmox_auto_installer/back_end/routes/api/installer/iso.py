import json
from pathlib import Path
from fastapi import Request
from logging import getLogger
from passlib.hash import sha512_crypt
from fastapi.responses import JSONResponse
from safe_pc.proxmox_auto_installer.answer_file.cached_answers import CacheManager
from safe_pc.proxmox_auto_installer.answer_file.answer_file import (
    ProxmoxAnswerFile,
    create_answer_file_from_dict,
)
from safe_pc.proxmox_auto_installer.back_end.iso_jobs import Job, below_max_jobs

LOGGER = getLogger("safe_pc.proxmox_auto_installer.routes.api.installer.iso")


CACHE_DIR = Path(__file__).parents[3] / "data" / "cached_answers"




async def check_max_jobs():
    if not await below_max_jobs():
        return JSONResponse(
            content={"error": "Maximum number of concurrent jobs reached."},
            status_code=429,
        )
    return None


async def post_installer_iso(request: Request) -> JSONResponse:

    try:
        cache_manager = await CacheManager.new() # type: ignore

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
        # check the cache to see if we already have an ISO for this answer file data
        file_hash =  answer_file.calculate_hash()
        job_id = await cache_manager.get_job_by_hash(file_hash) # type: ignore
        if job_id is not None and len(job_id) == 1: # type: ignore
            existing_iso_path = await cache_manager.get_iso_path(job_id=job_id[0]) # type: ignore
            if existing_iso_path is not None:
    
                # An answer file was cached, return the existing job ID
                LOGGER.info(
                    f"Answer file already cached, returning existing job ID for hash {file_hash}"
                )
                return JSONResponse(
                    {"status": "Not Modified", "jobId": f"{job_id[0]}", "isoPath": str(existing_iso_path)}, # type: ignore
                    status_code=304,
                )
        

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
