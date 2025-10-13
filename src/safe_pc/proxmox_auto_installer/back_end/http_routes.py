import re
from logging import getLogger
from safe_pc.proxmox_auto_installer.answer_file.cached_answers import CacheManager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

LOGGER = getLogger(__name__)


class HttpAPIRoutes:

    @staticmethod
    def register(
        app: FastAPI,
    ):
            
        @app.post("/api/prox/answer_file/{job_id}")
        async def get_answer_file(job_id: str, request:Request): # type: ignore
        
            try:
                LOGGER.info(f"Received request for answer file of job {job_id}")
                data = await request.json()
                cached_manager = await CacheManager.new()
                # grab the answer file bytes from cache - we need to modify the NIC filter line
                answer_bytes =  await cached_manager.read_answer_bytes(job_id=job_id)
                
                if not answer_bytes:
                    raise ValueError("Answer file is empty")      
                         
                # get the network interfaces from the request data
                net_i_faces = data.get("network_interfaces", [])
                if not net_i_faces or len(net_i_faces) == 0:
                    LOGGER.error("No network_interfaces provided in request data")
                    raise ValueError("No network_interfaces provided")
                
                # get the mac of the first interface
                m_face = net_i_faces[0]
                m_val = f"*{m_face.get('mac', '').replace(':', '').lower()}"
                
                # need the path for the FileResponse    
                answer_file_path = cached_manager.get_answer_path(job_id=job_id)
                if not answer_file_path:
                    raise ValueError("Answer file path not found") # shouldn't happen as we have the bytes
               
                # update NIC filter line (handles quoted or unquoted key)
                text = answer_bytes.decode("utf-8")
                text = re.sub(
                    r'^[\'"]?filter\.ID_NET_NAME_MAC[\'"]?\s*=\s*".*"$',
                    f'filter.ID_NET_NAME_MAC = "{m_val}"',
                    text,
                    flags=re.MULTILINE,
                )

                # write the updated answer file back to cache - write is atomic so
                # the client should receive the updated file
                updated_answer_bytes = text.encode("utf-8")
                await cached_manager.put_answer_bytes(job_id=job_id, data=updated_answer_bytes)            
            
                return FileResponse(answer_file_path, media_type="text/plain", filename="answer_file.toml")
            except Exception as e:
                LOGGER.error(f"Error retrieving answer file for job {job_id}: {e}")
                return JSONResponse(
                    {"error": f"Error retrieving answer file: {e}"},
                    status_code=500,
                )