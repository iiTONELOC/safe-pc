from safe_pc.proxmox_auto_installer.back_end.routes.api.installer.data import (
    installer_data,
)
from safe_pc.proxmox_auto_installer.back_end.routes.api.installer.iso import (
    installer_iso,
)

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates


class APIRoutes:

    @staticmethod
    def register(
        app: FastAPI,
        templates: Jinja2Templates,
        dev: bool = False,
    ):
        # return a 200 hello work json response for testing
        @app.get(path="/api/installer/data")
        def installer_data_route():
            return installer_data()

        @app.post(path="/api/installer/iso")
        async def installer_iso_route(request: Request):
            return await installer_iso(request)
