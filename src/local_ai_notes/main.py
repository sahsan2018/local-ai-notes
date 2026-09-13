from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .db import database_engine


def create_app(engine=None):
    engine = engine if engine is not None else database_engine()

    @asynccontextmanager
    async def lifespan(_app):
        yield
        engine.dispose()

    app = FastAPI(title="Local AI Notes", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    @app.get("/health/live")
    def live():
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready():
        try:
            with engine.connect() as connection:
                version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if version != "0001":
                    return JSONResponse({"status": "not_ready"}, status_code=503)
        except SQLAlchemyError:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    return app
