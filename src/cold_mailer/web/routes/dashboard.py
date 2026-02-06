"""Dashboard routes for Cold Mailer web UI."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..dependencies import get_rate_limiter, get_recruiter_manager

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    recruiter_manager=Depends(get_recruiter_manager),
    rate_limiter=Depends(get_rate_limiter),
):
    """Render the dashboard page with statistics."""
    templates = request.app.state.templates

    # Get statistics
    recruiter_stats = recruiter_manager.get_statistics()
    rate_stats = rate_limiter.get_statistics()
    recent_sent = rate_limiter.get_sent_history(5)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "recruiter_stats": recruiter_stats,
            "rate_stats": rate_stats,
            "recent_sent": recent_sent,
        },
    )
