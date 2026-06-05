import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.grocery_list import router as grocery_list_router
from app.api.health import router as health_router
from app.api.household import router as household_router
from app.api.ingredients import router as ingredients_router
from app.api.inventory import router as inventory_router
from app.api.matching import router as matching_router
from app.api.public_plan import router as public_plan_router
from app.api.recipes import router as recipes_router
from app.api.recipes import tag_router
from app.api.weeks import router as weeks_router
from app.core.config import settings
from app.core.middleware import SessionMiddleware
from app.core.security_headers import SecurityHeadersMiddleware

logger = logging.getLogger("chuchiplaner")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    state = "open" if settings.signup_enabled else "closed"
    logger.info("Startup: sign-ups are %s", state)
    yield


def create_app() -> FastAPI:
    if not settings.cors_origins and settings.signup_enabled:
        logger.warning(
            "Security: cors_origins is empty and signup_enabled is True. "
            "Set CHUCHI_CORS_ORIGINS to a comma-separated list of allowed "
            "origins, or set CHUCHI_SIGNUP_ENABLED=false."
        )

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SessionMiddleware)

    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(grocery_list_router, prefix="/api")
    app.include_router(ingredients_router, prefix="/api")
    app.include_router(inventory_router, prefix="/api")
    app.include_router(household_router, prefix="/api")
    app.include_router(matching_router, prefix="/api")
    app.include_router(public_plan_router, prefix="/api")
    app.include_router(recipes_router, prefix="/api")
    app.include_router(tag_router, prefix="/api")
    app.include_router(weeks_router, prefix="/api")

    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    if os.path.isdir(static_dir):
        app.mount(
            "/assets",
            StaticFiles(directory=os.path.join(static_dir, "assets")),
            name="assets",
        )
        @app.get("/{full_path:path}", response_class=FileResponse)
        async def serve_frontend(full_path: str) -> FileResponse:
            file_path = os.path.realpath(os.path.join(static_dir, full_path))
            if not file_path.startswith(os.path.realpath(static_dir) + os.sep):
                return FileResponse(os.path.join(static_dir, "index.html"))
            if os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(os.path.join(static_dir, "index.html"))

    app.add_middleware(SecurityHeadersMiddleware)

    return app


app = create_app()
