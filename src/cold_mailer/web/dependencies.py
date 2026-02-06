"""FastAPI dependency injection for Cold Mailer web UI."""

from fastapi import Request

from ..config import Config
from ..mailer import Mailer
from ..rate_limiter import RateLimiter
from ..recruiter_manager import RecruiterManager
from ..template_engine import TemplateEngine


def get_config(request: Request) -> Config:
    """Get Config instance from app state."""
    return request.app.state.config


def get_recruiter_manager(request: Request) -> RecruiterManager:
    """Get RecruiterManager instance."""
    config = get_config(request)
    return RecruiterManager(config)


def get_template_engine(request: Request) -> TemplateEngine:
    """Get TemplateEngine instance."""
    config = get_config(request)
    return TemplateEngine(config)


def get_mailer(request: Request) -> Mailer:
    """Get Mailer instance."""
    config = get_config(request)
    return Mailer(config)


def get_rate_limiter(request: Request) -> RateLimiter:
    """Get RateLimiter instance."""
    config = get_config(request)
    return RateLimiter(config)
