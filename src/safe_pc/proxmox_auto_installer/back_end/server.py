from asyncio import run
from pathlib import Path
from sys import exit, argv

from safe_pc.proxmox_auto_installer.utils.jwt import is_jwt_valid, jwt_middleware
from safe_pc.utils.utils import handle_keyboard_interrupt
from safe_pc.utils.crypto.temp_key_file import TempKeyFile
from safe_pc.utils.crypto.dpapi import read_dpapi_protected_key
from safe_pc.proxmox_auto_installer.back_end.routes.routes import PiRoutes

from uvicorn import Config, Server
from fastapi import FastAPI
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

_CURRENT_DIR = Path(__file__).resolve().parent
_MAIN = "safe_pc.proxmox_auto_installer.back_end.server:PiServer.create_app"
_DEV_MAIN = "safe_pc.proxmox_auto_installer.back_end.server:PiServer.create_app_dev"


class PiServer:
    CORS_ORIGINS = [
        "https://127.0.0.1",
        "https://127.0.0.1:33008",
    ]
    STATIC_DIR = str(object=_CURRENT_DIR.parent / "front_end" / "static")

    TEMPLATES = Jinja2Templates(
        directory=str(object=_CURRENT_DIR.parent / "front_end" / "templates")
    )

    @staticmethod
    def create_app(dev: bool = False) -> FastAPI:
        """Create a new FastAPI app.

        Args:
            dev (bool, optional): Optional flag to enable development features. Defaults to False.

        Returns:
            FastAPI: The created FastAPI app instance.

        Note:
            In development mode, the app includes hot-reloading capabilities for the frontend.
            This requires extra dependencies and should only be used during development.
            Specifically, `Node.js` with `npm`, `tailwindcss`, and `nodemon` are required.
            If node is already installed, ensure the dependencies are installed by navigating to
            `src/safe_pc/proxmox_auto_installer/front_end/tailwindcss` and running `npm install -D`.


        Usage:
        ```python
            # Programmatically
            from safe_pc.proxmox_auto_installer.back_end.server import PiServer
            PiServer.run(dev=True)   # For development mode w/ hot-reloading
            PiServer.run()           # For production mode

            # As a module
            # Note: `python` might be `python3` or `py` on some systems
            python -m safe_pc.proxmox_auto_installer.back_end.server # production mode
            python -m safe_pc.proxmox_auto_installer.back_end.server dev # development mode
        ```
        """
        app = FastAPI()
        app.add_middleware(
            middleware_class=CORSMiddleware,
            allow_origins=PiServer.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add JWT-Middleware here, to be used in routes
        app.middleware("http")(jwt_middleware)
        app.mount(
            path="/static",
            app=StaticFiles(directory=PiServer.STATIC_DIR),
            name="static",
        )

        # attaches the CSP middleware and the routes
        PiRoutes.register(app=app, templates=PiServer.TEMPLATES, dev=dev)

        return app

    @staticmethod
    def create_app_dev() -> FastAPI:
        """Shorthand for creating a development-mode app.

        Returns:
            FastAPI: a FastAPI app with development features enabled.
        """
        return PiServer.create_app(dev=True)

    @staticmethod
    async def run(dev: bool = False):
        """
        Asynchronously starts the server with the specified configuration.
        Args:
            dev (bool, optional): If True, runs the server in development mode using the development app configuration.
                If False, uses the main app configuration. Defaults to False.
        Raises:
            Exception: If an error occurs during server startup, prints the error and exits the process with code 1.
        """
        cert_dir = Path(__file__).resolve().parents[4] / "certs"
        with TempKeyFile(read_dpapi_protected_key(cert_dir / "key.pem")) as key_path:
            try:
                config = Config(
                    app=(_DEV_MAIN if dev else _MAIN),
                    port=33008,
                    factory=True,
                    log_level="info",
                    ssl_keyfile=str(object=key_path),
                    ssl_certfile=str(object=cert_dir / "cert.pem"),
                )
                server = Server(config=config)
                await server.serve()
            except Exception as e:
                print(f"Error starting server: {e}")
                exit(code=1)


@handle_keyboard_interrupt
def main():
    """
    Entry point for the server application. Initializes and runs the PiServer.
    """

    run(main=PiServer.run())


@handle_keyboard_interrupt
def main_dev():
    """
    Entry point for running the server in development mode with hot-reloading.
    """
    run(main=PiServer.run(dev=True))


# If running directly as a script, start the server
if __name__ == "__main__":

    args = argv
    if len(args) > 1 and args[1] == "dev":
        main_dev()
    else:
        main()
