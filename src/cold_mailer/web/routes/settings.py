"""Settings routes for Cold Mailer web UI."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from ..dependencies import get_config, get_mailer, get_rate_limiter

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    config=Depends(get_config),
    rate_limiter=Depends(get_rate_limiter),
):
    """Render the settings page."""
    templates = request.app.state.templates

    rate_stats = rate_limiter.get_statistics()
    sent_history = rate_limiter.get_sent_history(10)

    # Check if credentials are configured
    has_credentials = bool(config.env.gmail_email and config.env.gmail_app_password)

    return templates.TemplateResponse(
        "settings/index.html",
        {
            "request": request,
            "config": config,
            "rate_stats": rate_stats,
            "sent_history": sent_history,
            "has_credentials": has_credentials,
        },
    )


@router.post("/test-smtp", response_class=HTMLResponse)
async def test_smtp(
    request: Request,
    mailer=Depends(get_mailer),
):
    """Test SMTP connection (HTMX endpoint)."""
    success, message = mailer.test_connection()

    if success:
        return HTMLResponse(
            content=f'''
            <div class="p-4 rounded-lg bg-green-50 border border-green-200">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path>
                    </svg>
                    <span class="text-green-700 font-medium">Connection Successful</span>
                </div>
                <p class="mt-2 text-sm text-green-600">{message}</p>
            </div>
            ''',
            status_code=200,
        )
    else:
        return HTMLResponse(
            content=f'''
            <div class="p-4 rounded-lg bg-red-50 border border-red-200">
                <div class="flex items-center">
                    <svg class="w-5 h-5 text-red-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                    <span class="text-red-700 font-medium">Connection Failed</span>
                </div>
                <p class="mt-2 text-sm text-red-600">{message}</p>
            </div>
            ''',
            status_code=200,
        )


@router.post("/clear-history", response_class=HTMLResponse)
async def clear_history(
    request: Request,
    rate_limiter=Depends(get_rate_limiter),
):
    """Clear sent email history (HTMX endpoint)."""
    rate_limiter.clear_history()
    return HTMLResponse(
        content='''
        <div class="p-4 rounded-lg bg-green-50 border border-green-200">
            <p class="text-green-700">History cleared successfully.</p>
        </div>
        ''',
        status_code=200,
    )
