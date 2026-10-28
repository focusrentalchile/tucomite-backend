"""ASGI entry point for the Tu Comité API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import init_database
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    configure_logging()
    init_database()

    application = FastAPI(title=settings.app_name)
    application.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="tu_comite_session",
        same_site=settings.session_same_site,
        https_only=settings.session_https_only,
        max_age=60 * 60 * 12,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    return application


app = create_app()
