from datetime import datetime
from safe_pc.proxmox_auto_installer.back_end.helpers import DevHelpers
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


class BaseRoutes:
    START_YEAR = 2025  # Project start year for copyright
    CSP_POLICY = (
        "default-src 'self'; "
        "connect-src 'self' wss://127.0.0.1:33008; "
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

        Side Effects:
            - Adds middleware to set Content-Security-Policy headers.
            - Registers the root endpoint ("/") to serve the main HTML page.
            - In development mode, sets up hot-reloading functionality.

        Notes:
            The CSP policy is set to restrict resources to the same origin and allow images from
            data URIs.
        """

        # Middleware to add Content-Security-Policy headers, ensures this is attached first
        @app.middleware(middleware_type="http")
        async def csp_middleware(request: Request, call_next):
            response = await call_next(request)
            response.headers["Content-Security-Policy"] = BaseRoutes.CSP_POLICY
            return response

        # Root endpoint serving the main page
        @app.get(path="/", response_class=HTMLResponse)
        async def read_root(request: Request):
            return templates.TemplateResponse(
                name="/pages/main/index.html",
                context={
                    "request": request,
                    "start_year": BaseRoutes.START_YEAR,
                    "current_year": BaseRoutes.CURRENT_YEAR,
                },
            )

        # Development mode features - hot-reloading, etc.
        if dev:
            DevHelpers.handle_dev_hot_reload(app=app, templates=templates)
