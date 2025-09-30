from safe_pc.proxmox_auto_installer.back_end.routes.api.api import APIRoutes
from safe_pc.proxmox_auto_installer.back_end.routes.base import BaseRoutes
from fastapi import FastAPI
from fastapi.templating import Jinja2Templates


class PiRoutes:
    @staticmethod
    def register(
        app: FastAPI,
        templates: Jinja2Templates,
        dev: bool = False,
    ) -> None:
        "/"
        BaseRoutes.register(app=app, templates=templates, dev=dev)
        "/api"
        APIRoutes.register(app=app, templates=templates, dev=dev)
