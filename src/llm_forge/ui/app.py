"""Unified FastAPI application for llm-forge Web UI.

Serves both the REST API and static React frontend.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from llm_forge.ui.auth import ApiKeyMiddleware, ApiKeyStore
from llm_forge.ui.routes import training, datasets, experiments, evaluation
from llm_forge.ui.routes import export_routes, hardware
from llm_forge.ui.assistant import router as assistant_router
from llm_forge.ui.metrics import router as metrics_router
from llm_forge.ui.routes.compute import router as compute_router
from llm_forge.ui.routes.workflows import router as workflows_router
from llm_forge.ui.routes.prompts import router as prompts_router
from llm_forge.ui.routes.settings import router as settings_router
from llm_forge.ui.routes.runs import router as runs_router
from llm_forge.ui.routes.registry import router as registry_router
from llm_forge.ui.routes.serving import router as serving_router
from llm_forge.ui.routes.protocols import router as protocols_router
from llm_forge.ui.routes.pipeline_run import router as pipeline_run_router
from llm_forge.ui.routes.site_chat import router as site_chat_router

_env_file = os.environ.get("FORGE_ENV_FILE", "").strip()
if _env_file:
    load_dotenv(_env_file)  # Load explicit env profile when provided
else:
    load_dotenv()  # Fallback to default .env

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    """FastAPI lifespan: startup and shutdown hooks."""
    logger.info("llm-forge backend starting up")
    yield
    logger.info("llm-forge backend shutting down, cleaning up...")
    from llm_forge.ui.jobs import shutdown_executor

    shutdown_executor()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app with all routes mounted.
    """
    app = FastAPI(
        title="llm-forge",
        description="LLM fine-tuning dashboard",
        version="0.1.0",
        lifespan=_lifespan,
    )

    stand_mode = os.environ.get("FORGE_STAND_MODE", "dev").strip() or "dev"

    # CORS: configurable via FORGE_CORS_ORIGINS env var (comma-separated)
    cors_env = os.environ.get("FORGE_CORS_ORIGINS", "")
    cors_origins = (
        [o.strip() for o in cors_env.split(",") if o.strip()]
        if cors_env
        else ["http://localhost:3000", "http://localhost:8888"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # API key authentication (opt-in via FORGE_AUTH_ENABLED=true)
    auth_enabled = os.environ.get("FORGE_AUTH_ENABLED", "false").lower() == "true"
    key_store = ApiKeyStore()
    if auth_enabled:
        app.add_middleware(ApiKeyMiddleware, key_store=key_store, enabled=True)
        if not key_store.list_keys():
            initial_key = key_store.generate_key("default")
            logger.warning(
                "Auth enabled but no keys found. Generated default key: %s",
                initial_key,
            )
    # Store app config on state for settings routes
    app.state.key_store = key_store
    app.state.auth_enabled = auth_enabled
    app.state.stand_mode = stand_mode

    # Rate limiting
    limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    # API routes
    app.include_router(training.router, prefix="/api/v1")
    app.include_router(datasets.router, prefix="/api/v1")
    app.include_router(experiments.router, prefix="/api/v1")
    app.include_router(evaluation.router, prefix="/api/v1")
    app.include_router(export_routes.router, prefix="/api/v1")
    app.include_router(hardware.router, prefix="/api/v1")
    app.include_router(assistant_router, prefix="/api/v1")
    app.include_router(metrics_router, prefix="/api/v1")
    app.include_router(compute_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")
    app.include_router(prompts_router, prefix="/api/v1")
    app.include_router(settings_router, prefix="/api/v1")
    app.include_router(runs_router, prefix="/api/v1")
    app.include_router(registry_router, prefix="/api/v1")
    app.include_router(serving_router, prefix="/api/v1")
    app.include_router(protocols_router)
    app.include_router(pipeline_run_router)
    app.include_router(site_chat_router, prefix="/api/v1")

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "ok"}

    # Serve React static build if available (supports deep links like /experiments)
    if STATIC_DIR.exists():
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str):  # noqa: ANN202
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not Found")

            requested = STATIC_DIR / full_path
            if full_path and requested.is_file():
                return FileResponse(requested)

            return FileResponse(STATIC_DIR / "index.html")

    return app


def start_ui_server(host: str = "0.0.0.0", port: int = 8888) -> None:
    """Start the UI server with uvicorn.

    Args:
        host: Server host.
        port: Server port.
    """
    import uvicorn

    app = create_app()
    logger.info("Starting llm-forge UI on http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
