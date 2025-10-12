from asyncio import run
from pathlib import Path
from sys import exit, argv
import threading


from safe_pc.utils import (
    TempKeyFile,
    get_local_ip,
    handle_keyboard_interrupt,
)
from safe_pc.proxmox_auto_installer.utils import jwt_middleware
from safe_pc.proxmox_auto_installer.back_end.routes.api.installer.http import HttpAPIRoutes
from safe_pc.proxmox_auto_installer.back_end.routes.routes import PiRoutes

from fastapi import FastAPI
from dotenv import load_dotenv
from uvicorn import Config, Server
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from safe_pc.utils.logs import setup_logging


load_dotenv()

_CURRENT_DIR = Path(__file__).resolve().parent
_MAIN = "safe_pc.proxmox_auto_installer.back_end.server:PiServer.create_app"
_DEV_MAIN = "safe_pc.proxmox_auto_installer.back_end.server:PiServer.create_app_dev"

class HttpSever:
    IP = get_local_ip()
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
        """Starts the server with the specified configuration.
        """
        setup_logging()
       
        try:
            config = Config(
                app=HttpSever.create_app(),
                port=HttpSever.PORT,
                host=f"{HttpSever.IP}",
                log_level="info"
            )
            server = Server(config=config)
            run(server.serve())
        except Exception as e:
            print(f"Error starting server: {e}")
            exit(1)

# Proxmox Install Server
class PiServer:
    IP = get_local_ip()
    CORS_ORIGINS = [
        f"https://{IP}",
        f"https://{IP}:33008",
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
import threading
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
        setup_logging()
        cert_dir = Path(__file__).resolve().parents[4] / "certs"
        key_file_path = cert_dir / "safe-pc-key.pem"
        with TempKeyFile(
            key_file_path.read_bytes()
        ) as key_path:
            try:
                config = Config(
                    app=(_DEV_MAIN if dev else _MAIN),
                    port=33008,
                    host=f"{PiServer.IP}",
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
def run_both_servers():
    """
    Entry point for running both the HTTP and Proxmox Install servers concurrently.
    """

    run(main=HttpSever.run()) #type: ignore
    run(main=PiServer.run())
    
@handle_keyboard_interrupt
def run_both_servers_dev():
    """
    Entry point for running both the HTTP and Proxmox Install servers in development mode with hot-reloading.
    """

    http_thread = threading.Thread(target=lambda: run(HttpSever.run()), daemon=True) #type: ignore
    pi_thread = threading.Thread(target=lambda: run(PiServer.run()), daemon=True)

    http_thread.start()
    pi_thread.start()

    http_thread.join()
    pi_thread.join()

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
        run_both_servers_dev()
    else:
        run_both_servers()
