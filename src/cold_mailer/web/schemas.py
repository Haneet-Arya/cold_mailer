"""Pydantic schemas for request/response models."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RecruiterCreate(BaseModel):
    """Schema for creating a new recruiter."""

    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(default="", max_length=100)
    company: str = Field(..., min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=20)
    job_title: str = Field(default="", max_length=200)
    department: str = Field(default="", max_length=100)
    greeting_style: Literal["formal", "semi_formal", "casual", "professional"] = "semi_formal"
    custom_fields: dict[str, str] = Field(default_factory=dict)


class RecruiterUpdate(BaseModel):
    """Schema for updating a recruiter."""

    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    company: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=20)
    job_title: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=100)
    greeting_style: Literal["formal", "semi_formal", "casual", "professional"] | None = None
    status: Literal["pending", "sent", "replied", "bounced"] | None = None
    custom_fields: dict[str, str] | None = None


class SendEmailRequest(BaseModel):
    """Schema for sending an email."""

    recruiter_id: str
    template_name: str
    custom_vars: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False


class BulkSendRequest(BaseModel):
    """Schema for bulk email sending."""

    template_name: str | None = None
    custom_vars: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False


class MessageResponse(BaseModel):
    """Generic message response."""

    success: bool
    message: str


class BulkSendProgress(BaseModel):
    """Progress update for bulk email sending."""

    session_id: str
    current: int
    total: int
    current_email: str
    status: Literal["pending", "in_progress", "completed", "error"]
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[dict] = Field(default_factory=list)
