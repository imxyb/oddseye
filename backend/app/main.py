from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.db.models  # noqa: F401
from app.api.routes import auth, health, markets, paper, radar, settings, signals
from app.core.config import get_settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    settings_obj = get_settings()
    configure_logging(settings_obj.log_level)
    app = FastAPI(title="Prediction Radar API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(radar.router)
    app.include_router(markets.router)
    app.include_router(signals.router)
    app.include_router(paper.router)
    app.include_router(settings.router)
    return app


app = create_app()

