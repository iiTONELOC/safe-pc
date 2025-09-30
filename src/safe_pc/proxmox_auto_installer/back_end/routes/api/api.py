from fastapi import FastAPI
from fastapi.templating import Jinja2Templates


class APIRoutes:
    @staticmethod
    def register(
        app: FastAPI,
        templates: Jinja2Templates,
        dev: bool = False,
    ):
        # return a 200 hello work json response for testing
        @app.get(path="/api/hello")
        async def read_root():
            return {"message": "Hello, World!"}
