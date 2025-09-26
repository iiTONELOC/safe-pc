from pathlib import Path
from asyncio import run
from importlib import reload
from uvicorn import Config, Server
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request, Response
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware


CSP_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
)

CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:3308",
    "http://127.0.0.1",
    "http://127.0.0.1:3308",
    "http://[::1]",
    "http://[::1]:3308",
]

CURRENT_DIR = Path(__file__).resolve().parent

TEMPLATES = Jinja2Templates(
    directory=str(object=CURRENT_DIR.parent / "front_end" / "templates")
)
STATIC_DIR = str(object=CURRENT_DIR.parent / "front_end" / "static")


def create_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        middleware_class=CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount(path="/static", app=StaticFiles(directory=STATIC_DIR), name="static")

    @app.middleware(middleware_type="http")
    async def add_csp_header(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP_POLICY
        return response

    @app.get("/", response_class=HTMLResponse)
    async def read_root(request: Request):
        return TEMPLATES.TemplateResponse(
            name="base.html", context={"request": request}
        )

    return app


async def run_server():

    try:
        config = Config(
            port=3308,
            reload=True,
            factory=True,
            log_level="info",
            reload_dirs=[str(object=CURRENT_DIR.parent.parent)],
            app="safe_pc.proxmox_auto_installer.back_end.server:create_app",
        )
        server = Server(config=config)
        await server.serve()
    except Exception as e:
        if Exception == KeyboardInterrupt:
            print("Server stopped by user")
        else:
            print(f"Error starting server: {e}")
            exit(code=1)


def main():
    run(main=run_server())


if __name__ == "__main__":
    main()
