from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


class PiRoutes:
    CSP_POLICY = (
        "default-src 'self'; "
        "connect-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
    )

    @staticmethod
    def register_routes(
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

        Notes:
            The CSP policy is set to restrict resources to the same origin and allow images from
            data URIs.
        """

        @app.middleware(middleware_type="http")
        async def csp_middleware(request: Request, call_next):
            response = await call_next(request)
            response.headers["Content-Security-Policy"] = PiRoutes.CSP_POLICY
            return response

        @app.get(path="/", response_class=HTMLResponse)
        async def read_root(request: Request):
            return templates.TemplateResponse(
                name="base.html", context={"request": request}
            )
