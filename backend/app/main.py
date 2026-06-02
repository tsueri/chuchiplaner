import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.household import router as household_router
from app.api.ingredients import router as ingredients_router
from app.api.recipes import router as recipes_router
from app.core.config import settings
from app.core.middleware import SessionMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version)

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
    app.include_router(ingredients_router, prefix="/api")
    app.include_router(household_router, prefix="/api")
    app.include_router(recipes_router, prefix="/api")

    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    if os.path.isdir(static_dir):
        app.mount(
            "/assets",
            StaticFiles(directory=os.path.join(static_dir, "assets")),
            name="assets",
        )
        app.mount(
            "/", StaticFiles(directory=static_dir, html=True), name="static"
        )

    return app


app = create_app()
