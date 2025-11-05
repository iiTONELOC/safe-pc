import threading
from asyncio import run
from pathlib import Path
from sys import exit, argv


from utm.utils import (
    TempKeyFile,
    # get_local_ip,
    generate_self_signed_cert,
    handle_keyboard_interrupt,
)
from proxmox_auto_installer.utils import jwt_middleware

from proxmox_auto_installer.back_end.https_routes import HttpsRoutes
from proxmox_auto_installer.back_end.http_routes import HttpAPIRoutes

from fastapi import FastAPI
from dotenv import load_dotenv
from uvicorn import Config, Server
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from utm.__main__ import setup_logging


load_dotenv()


_CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MAIN = "proxmox_auto_installer.back_end.server:ProxHttpsServer.create_app"
_DEV_MAIN = "proxmox_auto_installer.back_end.server:ProxHttpsServer.create_app_dev"


class ProxHttpSever:
    # IP = get_local_ip()
    IP = "0.0.0.0"
    PORT = 33007

    @staticmethod
    def create_app() -> FastAPI:
        """Create a new FastAPI app.

        Returns:
            FastAPI: The created FastAPI app instance.
        """
        app = FastAPI()

        HttpAPIRoutes.register(app=app)

        return app

    @staticmethod
    def run():
        """Starts the server with the specified configuration."""
        setup_logging()

        try:
            config = Config(
                app=ProxHttpSever.create_app(),
                port=ProxHttpSever.PORT,
                host=f"{ProxHttpSever.IP}",
                log_level="info",
            )
            server = Server(config=config)
            run(server.serve())
        except Exception as e:
            print(f"Error starting server: {e}")
            exit(1)


# Proxmox Install Server
class ProxHttpsServer:
    # IP = get_local_ip()
    IP = "0.0.0.0"
    CORS_ORIGINS = [
        f"https://{IP}",
        f"https://{IP}:33008",
    ]
    STATIC_DIR = str(object=_CURRENT_DIR.parent / "front_end" / "static")

    TEMPLATES = Jinja2Templates(directory=str(object=_CURRENT_DIR.parent / "front_end" / "templates"))

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
            from proxmox_auto_installer.back_end.server import ProxHttpsServer
            import threading
            ProxHttpsServer.run(dev=True)   # For development mode w/ hot-reloading
            ProxHttpsServer.run()           # For production mode

            # As a module
            # Note: `python` might be `python3` or `py` on some systems
            python -m proxmox_auto_installer.back_end.server # production mode
            python -m proxmox_auto_installer.back_end.server dev # development mode
        ```
        """
        app = FastAPI()

        app.add_middleware(
            middleware_class=CORSMiddleware,
            allow_origins=ProxHttpsServer.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        app.middleware("http")(jwt_middleware)
        app.mount(
            path="/static",
            app=StaticFiles(directory=ProxHttpsServer.STATIC_DIR),
            name="static",
        )

        # attaches the CSP middleware and the routes
        HttpsRoutes.register(app=app, templates=ProxHttpsServer.TEMPLATES, dev=dev)

        return app

    @staticmethod
    def create_app_dev() -> FastAPI:
        """Shorthand for creating a development-mode app.

        Returns:
            FastAPI: a FastAPI app with development features enabled.
        """
        return ProxHttpsServer.create_app(dev=True)

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
        setup_logging()
        cert_dir = Path(__file__).resolve().parents[3] / "certs"
        key_file_path = cert_dir / "safe-pc-key.pem"
        # if the key file does not exist - create the certs
        if not key_file_path.exists():
            generate_self_signed_cert(**{"common_name": ProxHttpsServer.IP, "state": "FL", "locality": "Orlando"})

        with TempKeyFile(key_file_path.read_bytes()) as key_path:
            try:
                config = Config(
                    app=(_DEV_MAIN if dev else _MAIN),
                    port=33008,
                    host=f"{ProxHttpsServer.IP}",
                    factory=True,
                    log_level="info",
                    ssl_keyfile=str(object=key_path),
                    ssl_certfile=str(object=cert_dir / "safe-pc-cert.pem"),
                )
                server = Server(config=config)
                await server.serve()
            except Exception as e:
                print(f"Error starting server: {e}")
                exit(1)


@handle_keyboard_interrupt
def main():
    """
    Entry point for the backend servers
    """
    answer_server_thread = threading.Thread(target=lambda: run(ProxHttpSever.run()), daemon=True)  # type: ignore
    ui_api_server_thread = threading.Thread(target=lambda: run(ProxHttpsServer.run()), daemon=True)

    answer_server_thread.start()
    ui_api_server_thread.start()

    answer_server_thread.join()
    ui_api_server_thread.join()


@handle_keyboard_interrupt
def main_dev():
    """
    Entry point for running the server in development mode with hot-reloading.
    """

    answer_server_thread = threading.Thread(target=lambda: run(ProxHttpSever.run()), daemon=True)  # type: ignore
    ui_api_server_thread = threading.Thread(target=lambda: run(ProxHttpsServer.run()), daemon=True)

    answer_server_thread.start()
    ui_api_server_thread.start()

    answer_server_thread.join()
    ui_api_server_thread.join()


# If running directly as a script, start the server
if __name__ == "__main__":

    args = argv
    if len(args) > 1 and args[1] == "dev":
        main_dev()
    else:
        main()
