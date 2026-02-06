"""Email template routes for Cold Mailer web UI."""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..dependencies import get_recruiter_manager, get_template_engine

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def list_templates(
    request: Request,
    template_engine=Depends(get_template_engine),
):
    """List all available email templates."""
    templates = request.app.state.templates

    template_list = template_engine.list_templates()
    template_info = []

    for name in template_list:
        path = template_engine.get_template_path(name)
        try:
            variables = template_engine.get_template_variables(name)
        except Exception:
            variables = []

        template_info.append({
            "name": name,
            "path": str(path),
            "variables": variables,
        })

    return templates.TemplateResponse(
        "email_templates/list.html",
        {
            "request": request,
            "templates": template_info,
        },
    )


@router.get("/{template_name}/preview", response_class=HTMLResponse)
async def preview_template(
    request: Request,
    template_name: str,
    template_engine=Depends(get_template_engine),
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Preview an email template with sample data."""
    templates = request.app.state.templates

    if not template_engine.template_exists(template_name):
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

    # Get a sample recruiter or create dummy data
    all_recruiters = recruiter_manager.get_all()
    if all_recruiters:
        sample_recruiter = all_recruiters[0]
    else:
        # Create a dummy recruiter for preview
        from ...recruiter_manager import Recruiter
        sample_recruiter = Recruiter(
            id="0",
            email="john.doe@example.com",
            first_name="John",
            last_name="Doe",
            title="Mr.",
            company="Example Corp",
            job_title="Software Engineer",
            department="Engineering",
            greeting_style="semi_formal",
            custom_fields={"skills": "Python, JavaScript", "referral": "Jane Smith"},
        )

    try:
        preview = template_engine.render_preview(template_name, sample_recruiter)
        subject, body = template_engine.render(template_name, sample_recruiter)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error rendering template: {e}")

    # Read the raw template content
    template_path = template_engine.get_template_path(template_name)
    raw_content = template_path.read_text()

    return templates.TemplateResponse(
        "email_templates/preview.html",
        {
            "request": request,
            "template_name": template_name,
            "subject": subject,
            "body": body,
            "raw_content": raw_content,
            "sample_recruiter": sample_recruiter,
        },
    )


@router.get("/{template_name}/content", response_class=HTMLResponse)
async def get_template_content(
    template_name: str,
    template_engine=Depends(get_template_engine),
):
    """Get raw template content (for HTMX)."""
    if not template_engine.template_exists(template_name):
        raise HTTPException(status_code=404, detail=f"Template '{template_name}' not found")

    template_path = template_engine.get_template_path(template_name)
    content = template_path.read_text()

    return HTMLResponse(content=f"<pre><code>{content}</code></pre>")
