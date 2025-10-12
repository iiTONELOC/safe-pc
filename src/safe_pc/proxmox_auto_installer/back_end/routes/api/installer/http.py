import re
from logging import getLogger
from safe_pc.proxmox_auto_installer.answer_file.cached_answers import CacheManager


from fastapi.responses import FileResponse, JSONResponse

from fastapi import FastAPI, Request
LOGGER = getLogger("safe_pc.proxmox_auto_installer.routes.api")


class HttpAPIRoutes:

    @staticmethod
    def register(
        app: FastAPI,
    ):
            
        @app.post("/api/prox/answer_file/{job_id}")
        async def get_answer_file(job_id: str, request:Request): # type: ignore
            LOGGER.info(f"Received request for answer file of job {job_id}")
            data = await request.json()
            LOGGER.info(f"Request data: {data}")
            
            cached_manager = await CacheManager.new()
            answer_file_path = await cached_manager.get_answer_path(job_id=job_id)
            if not answer_file_path or not answer_file_path.exists():
                return JSONResponse(
                    {"error": f"No cached answer file found for job {job_id}"},
                    status_code=404,
                )
            try:
                answer_bytes = await cached_manager.read_answer_bytes(job_id=job_id)
                if not answer_bytes:
                    raise ValueError("Answer file is empty")
            
                        
                text = answer_bytes.decode("utf-8")
                net_ifaces = data.get("network_interfaces", [])
                if not net_ifaces or len(net_ifaces) == 0:
                    LOGGER.warning("No network_interfaces provided in request data")
                    return FileResponse(answer_file_path, media_type="text/plain", filename="answer_file.toml")
                
                m_face = net_ifaces[0]
                LOGGER.info(f"Interfaces provided: {net_ifaces}")
                LOGGER.info(f"Using network interface for MAC filtering: {m_face}")
                m_val = f"*{m_face.get('mac', '').replace(':', '').lower()}"

                # update NIC filter line (handles quoted or unquoted key)
                text = re.sub(
                    r'^[\'"]?filter\.ID_NET_NAME_MAC[\'"]?\s*=\s*".*"$',
                    f'filter.ID_NET_NAME_MAC = "{m_val}"',
                    text,
                    flags=re.MULTILINE,
                )

                updated_answer_bytes = text.encode("utf-8")
                await cached_manager.update_answer_bytes(job_id=job_id, data=updated_answer_bytes)
            
            
                return FileResponse(answer_file_path, media_type="text/plain", filename="answer_file.toml")
            except Exception as e:
                LOGGER.error(f"Error retrieving answer file for job {job_id}: {e}")
                return JSONResponse(
                    {"error": f"Error retrieving answer file: {e}"},
                    status_code=500,
                )