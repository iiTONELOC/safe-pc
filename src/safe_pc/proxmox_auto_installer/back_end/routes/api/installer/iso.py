import json
from fastapi import Request
from fastapi.responses import JSONResponse


async def installer_iso(request: Request):

    try:
        req_body = await request.body()
        data = json.loads(req_body)
        print(f"Received ISO creation request with data: {json.dumps(data, indent=2)}")

        return JSONResponse({"status": "ISO creation started"})
    except Exception as _:
        return JSONResponse(content={"error": "Internal Server Error"}, status_code=500)
