from asyncio import timeout
from fastapi.templating import Jinja2Templates
from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect


async def _send_safe(ws: WebSocket, msg: str):
    try:
        async with timeout(1.0):
            await ws.send_text(msg)
        return True
    except Exception:
        return False


async def _trigger_reload(clients: set[WebSocket]):
    for ws in clients:
        ok = await _send_safe(ws, "reload")
        if not ok:
            clients.discard(ws)


# Used in development mode to handle hot-reloading of the frontend
class DevHelpers:
    reload_clients: set[WebSocket] = set()

    @staticmethod
    def handle_dev_hot_reload(app: FastAPI, templates=Jinja2Templates):
        """
        Sets up development hot-reload functionality for a FastAPI application.
        This function modifies the provided Jinja2Templates instance to indicate development mode,
        and registers two endpoints on the FastAPI app:
          - A WebSocket endpoint at '/reload-ws' that allows clients to listen for reload events.
          - A POST endpoint at '/trigger-reload' that triggers a reload event for all connected clients.
        Args:
            app (FastAPI): The FastAPI application instance to which the endpoints will be added.
            templates (Jinja2Templates, optional): The Jinja2Templates instance used for rendering templates.
                The default is the Jinja2Templates class itself.
        Side Effects:
            - Modifies the Jinja2 environment globals to set 'DEV' to True.
            - Registers new endpoints on the FastAPI app.
            - Manages a set of connected WebSocket clients for reload notifications.

        Notes:
            The frontend ws logic is in `static/js/utils/hot-reload.js`. Very basic script that connects to the ws
            and listens for "reload" messages, upon which it reloads the page.
        """

        templates.env.globals["DEV"] = True  # Mark templates as in dev mode

        @app.websocket(
            "/reload-ws", name="WebSocket for hot-reloading in development mode"
        )
        async def reload_ws(ws: WebSocket):
            await ws.accept()
            DevHelpers.reload_clients.add(ws)
            try:
                while True:
                    await ws.receive_text()
            except WebSocketDisconnect:
                pass
            finally:
                DevHelpers.reload_clients.remove(ws)

        @app.post("/trigger-reload")
        async def trigger_reload_endpoint():
            await _trigger_reload(DevHelpers.reload_clients)
            return Response(content="Reload triggered", media_type="text/plain")
