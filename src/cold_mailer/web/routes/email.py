"""Email sending routes for Cold Mailer web UI."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from ...exceptions import RecruiterNotFoundError
from ..dependencies import get_mailer, get_rate_limiter, get_recruiter_manager, get_template_engine
from .. import sse

router = APIRouter()

# Thread pool for running sync email operations
_executor = ThreadPoolExecutor(max_workers=2)


@router.get("/send", response_class=HTMLResponse)
async def send_email_form(
    request: Request,
    recruiter_id: str | None = None,
    template_engine=Depends(get_template_engine),
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Render the send email form."""
    templates = request.app.state.templates

    template_list = template_engine.list_templates()
    recruiters = recruiter_manager.get_all()

    selected_recruiter = None
    if recruiter_id:
        try:
            selected_recruiter = recruiter_manager.get_by_id(recruiter_id)
        except RecruiterNotFoundError:
            pass

    return templates.TemplateResponse(
        "email/send.html",
        {
            "request": request,
            "templates": template_list,
            "recruiters": recruiters,
            "selected_recruiter": selected_recruiter,
        },
    )


@router.post("/send")
async def send_email(
    request: Request,
    recruiter_id: str = Form(...),
    template_name: str = Form(...),
    dry_run: bool = Form(False),
    mailer=Depends(get_mailer),
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Send an email to a single recruiter."""
    templates = request.app.state.templates

    try:
        recruiter = recruiter_manager.get_by_id(recruiter_id)
    except RecruiterNotFoundError:
        raise HTTPException(status_code=404, detail="Recruiter not found")

    if dry_run:
        # Preview mode
        preview = mailer.preview_email(recruiter, template_name)
        return templates.TemplateResponse(
            "email/preview.html",
            {
                "request": request,
                "preview": preview,
                "recruiter": recruiter,
                "template_name": template_name,
            },
        )

    # Actually send the email
    try:
        success, message = mailer.send_email(recruiter, template_name)
        return templates.TemplateResponse(
            "email/result.html",
            {
                "request": request,
                "success": success,
                "message": message,
                "recruiter": recruiter,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "email/result.html",
            {
                "request": request,
                "success": False,
                "message": str(e),
                "recruiter": recruiter,
            },
        )


@router.get("/bulk", response_class=HTMLResponse)
async def bulk_send_form(
    request: Request,
    template_engine=Depends(get_template_engine),
    recruiter_manager=Depends(get_recruiter_manager),
    rate_limiter=Depends(get_rate_limiter),
):
    """Render the bulk send form."""
    templates = request.app.state.templates

    template_list = template_engine.list_templates()
    pending_recruiters = recruiter_manager.get_pending()
    rate_stats = rate_limiter.get_statistics()

    return templates.TemplateResponse(
        "email/bulk.html",
        {
            "request": request,
            "templates": template_list,
            "pending_count": len(pending_recruiters),
            "pending_recruiters": pending_recruiters,
            "rate_stats": rate_stats,
        },
    )


def _run_bulk_send(session_id: str, mailer, template_name: str, dry_run: bool):
    """Run bulk email send in background thread."""
    pending = mailer.recruiter_manager.get_pending()

    if not pending:
        sse.update_session(session_id, status="completed", current=0)
        return

    sse.update_session(session_id, status="in_progress", current=0)

    sent = 0
    failed = 0
    skipped = 0

    for i, recruiter in enumerate(pending):
        sse.update_session(
            session_id,
            current=i + 1,
            current_email=recruiter.email,
        )

        can_send, reason = mailer.rate_limiter.can_send()
        if not can_send:
            skipped += 1
            sse.update_session(
                session_id,
                skipped=skipped,
                error={"email": recruiter.email, "error": f"Rate limit: {reason}"},
            )
            continue

        try:
            success, message = mailer.send_email(recruiter, template_name, dry_run=dry_run)
            if success:
                sent += 1
            else:
                failed += 1
                sse.update_session(
                    session_id,
                    error={"email": recruiter.email, "error": message},
                )
        except Exception as e:
            failed += 1
            sse.update_session(
                session_id,
                error={"email": recruiter.email, "error": str(e)},
            )

        sse.update_session(session_id, sent=sent, failed=failed, skipped=skipped)

        # Wait between emails (but not after the last one)
        if not dry_run and i < len(pending) - 1:
            mailer.rate_limiter.wait_for_delay()

    sse.update_session(session_id, status="completed")


@router.post("/bulk/start")
async def start_bulk_send(
    request: Request,
    background_tasks: BackgroundTasks,
    template_name: str = Form(...),
    dry_run: bool = Form(False),
    mailer=Depends(get_mailer),
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Start a bulk email send operation."""
    templates = request.app.state.templates

    pending = recruiter_manager.get_pending()
    if not pending:
        return templates.TemplateResponse(
            "email/bulk_result.html",
            {
                "request": request,
                "error": "No pending recruiters to send to.",
            },
        )

    # Create session
    session = sse.create_session(total=len(pending))

    # Start background task
    loop = asyncio.get_event_loop()
    loop.run_in_executor(
        _executor,
        _run_bulk_send,
        session.session_id,
        mailer,
        template_name,
        dry_run,
    )

    return templates.TemplateResponse(
        "email/progress.html",
        {
            "request": request,
            "session_id": session.session_id,
            "total": len(pending),
            "dry_run": dry_run,
        },
    )


@router.get("/bulk/progress/{session_id}")
async def get_bulk_progress(session_id: str):
    """Get SSE stream for bulk send progress."""
    return sse.create_sse_response(session_id)


@router.get("/bulk/status/{session_id}", response_class=HTMLResponse)
async def get_bulk_status(request: Request, session_id: str):
    """Get current status of bulk send (for HTMX polling fallback)."""
    templates = request.app.state.templates
    session = sse.get_session(session_id)

    if not session:
        return HTMLResponse(content="<div>Session not found</div>", status_code=404)

    return templates.TemplateResponse(
        "email/progress_status.html",
        {
            "request": request,
            "session": session.to_dict(),
        },
    )
