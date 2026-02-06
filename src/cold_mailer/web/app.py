"""FastAPI application factory for Cold Mailer web UI."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..config import Config, get_config
from ..exceptions import ColdMailerError
from .routes import dashboard, email, recruiters, settings, templates


def create_app(project_root: Path | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Cold Mailer",
        description="Web UI for sending personalized cold emails to recruiters",
        version="1.0.0",
    )

    # Store config in app state
    config = get_config(project_root)
    app.state.config = config
    app.state.project_root = config.project_root

    # Setup templates
    templates_path = Path(__file__).parent / "templates"
    app.state.templates = Jinja2Templates(directory=str(templates_path))

    # Mount static files
    static_path = Path(__file__).parent / "static"
    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Include routers
    app.include_router(dashboard.router)
    app.include_router(recruiters.router, prefix="/recruiters", tags=["recruiters"])
    app.include_router(templates.router, prefix="/templates", tags=["templates"])
    app.include_router(email.router, prefix="/email", tags=["email"])
    app.include_router(settings.router, prefix="/settings", tags=["settings"])

    # Global exception handler for ColdMailerError
    @app.exception_handler(ColdMailerError)
    async def cold_mailer_exception_handler(request: Request, exc: ColdMailerError):
        """Handle Cold Mailer specific exceptions."""
        templates = app.state.templates
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error_title": exc.__class__.__name__,
                "error_message": str(exc),
            },
            status_code=400,
        )

    return app
