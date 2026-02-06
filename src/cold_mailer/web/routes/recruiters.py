"""Recruiter routes for Cold Mailer web UI."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from ...exceptions import DuplicateRecruiterError, RecruiterNotFoundError
from ..dependencies import get_recruiter_manager
from ..schemas import RecruiterCreate, RecruiterUpdate

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def list_recruiters(
    request: Request,
    status: str = "all",
    recruiter_manager=Depends(get_recruiter_manager),
):
    """List all recruiters with optional status filter."""
    templates = request.app.state.templates

    if status == "all":
        recruiters = recruiter_manager.get_all()
    else:
        recruiters = recruiter_manager.get_by_status(status)

    stats = recruiter_manager.get_statistics()

    return templates.TemplateResponse(
        "recruiters/list.html",
        {
            "request": request,
            "recruiters": recruiters,
            "current_status": status,
            "stats": stats,
        },
    )


@router.get("/add", response_class=HTMLResponse)
async def add_recruiter_form(request: Request):
    """Render the add recruiter form."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        "recruiters/form.html",
        {
            "request": request,
            "recruiter": None,
            "action": "add",
            "errors": {},
        },
    )


@router.post("/add")
async def create_recruiter(
    request: Request,
    email: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(""),
    company: str = Form(...),
    title: str = Form(""),
    job_title: str = Form(""),
    department: str = Form(""),
    greeting_style: str = Form("semi_formal"),
    custom_field_keys: list[str] = Form(default=[]),
    custom_field_values: list[str] = Form(default=[]),
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Create a new recruiter."""
    templates = request.app.state.templates

    # Build custom fields from parallel arrays
    custom_fields = {}
    for key, value in zip(custom_field_keys, custom_field_values):
        if key.strip() and value.strip():
            custom_fields[key.strip()] = value.strip()

    try:
        recruiter_manager.add(
            email=email,
            first_name=first_name,
            last_name=last_name,
            company=company,
            title=title if title else None,
            job_title=job_title,
            department=department,
            greeting_style=greeting_style,
            custom_fields=custom_fields,
        )
        return RedirectResponse(url="/recruiters?success=created", status_code=303)

    except DuplicateRecruiterError as e:
        return templates.TemplateResponse(
            "recruiters/form.html",
            {
                "request": request,
                "recruiter": None,
                "action": "add",
                "errors": {"email": str(e)},
                "form_data": {
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "company": company,
                    "title": title,
                    "job_title": job_title,
                    "department": department,
                    "greeting_style": greeting_style,
                },
            },
            status_code=400,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "recruiters/form.html",
            {
                "request": request,
                "recruiter": None,
                "action": "add",
                "errors": {"general": str(e)},
                "form_data": {
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "company": company,
                    "title": title,
                    "job_title": job_title,
                    "department": department,
                    "greeting_style": greeting_style,
                },
            },
            status_code=400,
        )


@router.get("/{recruiter_id}", response_class=HTMLResponse)
async def get_recruiter(
    request: Request,
    recruiter_id: str,
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Get a single recruiter's details."""
    templates = request.app.state.templates

    try:
        recruiter = recruiter_manager.get_by_id(recruiter_id)
    except RecruiterNotFoundError:
        raise HTTPException(status_code=404, detail="Recruiter not found")

    return templates.TemplateResponse(
        "recruiters/detail.html",
        {
            "request": request,
            "recruiter": recruiter,
        },
    )


@router.get("/{recruiter_id}/edit", response_class=HTMLResponse)
async def edit_recruiter_form(
    request: Request,
    recruiter_id: str,
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Render the edit recruiter form."""
    templates = request.app.state.templates

    try:
        recruiter = recruiter_manager.get_by_id(recruiter_id)
    except RecruiterNotFoundError:
        raise HTTPException(status_code=404, detail="Recruiter not found")

    return templates.TemplateResponse(
        "recruiters/form.html",
        {
            "request": request,
            "recruiter": recruiter,
            "action": "edit",
            "errors": {},
        },
    )


@router.post("/{recruiter_id}/edit")
async def update_recruiter(
    request: Request,
    recruiter_id: str,
    email: str = Form(...),
    first_name: str = Form(...),
    last_name: str = Form(""),
    company: str = Form(...),
    title: str = Form(""),
    job_title: str = Form(""),
    department: str = Form(""),
    greeting_style: str = Form("semi_formal"),
    status: str = Form("pending"),
    custom_field_keys: list[str] = Form(default=[]),
    custom_field_values: list[str] = Form(default=[]),
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Update a recruiter."""
    templates = request.app.state.templates

    # Build custom fields from parallel arrays
    custom_fields = {}
    for key, value in zip(custom_field_keys, custom_field_values):
        if key.strip() and value.strip():
            custom_fields[key.strip()] = value.strip()

    try:
        recruiter_manager.update(
            recruiter_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            company=company,
            title=title if title else None,
            job_title=job_title,
            department=department,
            greeting_style=greeting_style,
            status=status,
            custom_fields=custom_fields,
        )
        return RedirectResponse(url="/recruiters?success=updated", status_code=303)

    except RecruiterNotFoundError:
        raise HTTPException(status_code=404, detail="Recruiter not found")
    except Exception as e:
        recruiter = recruiter_manager.get_by_id(recruiter_id)
        return templates.TemplateResponse(
            "recruiters/form.html",
            {
                "request": request,
                "recruiter": recruiter,
                "action": "edit",
                "errors": {"general": str(e)},
            },
            status_code=400,
        )


@router.delete("/{recruiter_id}")
async def delete_recruiter(
    recruiter_id: str,
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Delete a recruiter (HTMX endpoint)."""
    try:
        recruiter_manager.delete(recruiter_id)
        return HTMLResponse(content="", status_code=200)
    except RecruiterNotFoundError:
        raise HTTPException(status_code=404, detail="Recruiter not found")


@router.post("/{recruiter_id}/status")
async def update_status(
    recruiter_id: str,
    status: str = Form(...),
    recruiter_manager=Depends(get_recruiter_manager),
):
    """Update recruiter status (HTMX endpoint)."""
    try:
        recruiter = recruiter_manager.update_status(recruiter_id, status)
        return HTMLResponse(
            content=f'<span class="status-badge status-{recruiter.status}">{recruiter.status}</span>',
            status_code=200,
        )
    except RecruiterNotFoundError:
        raise HTTPException(status_code=404, detail="Recruiter not found")
