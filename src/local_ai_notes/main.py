import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .db import database_engine
from .export_web import install_export_web
from .history_web import install_history_web
from .web import install_web


def create_app(engine=None, cookie_secure=None):
    engine = engine if engine is not None else database_engine()
    if cookie_secure is None:
        cookie_secure = os.environ.get("LOCAL_AI_NOTES_COOKIE_SECURE", "true").lower() not in {"0", "false", "no"}

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
                if version != "0002":
                    return JSONResponse({"status": "not_ready"}, status_code=503)
        except SQLAlchemyError:
            return JSONResponse({"status": "not_ready"}, status_code=503)
        return {"status": "ready"}

    install_web(app, engine, cookie_secure=cookie_secure)
    install_export_web(app, engine)
    install_history_web(app, engine)
    return app
