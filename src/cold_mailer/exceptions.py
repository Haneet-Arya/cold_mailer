"""Custom exceptions for Cold Mailer."""


class ColdMailerError(Exception):
    """Base exception for Cold Mailer."""

    pass


class ConfigurationError(ColdMailerError):
    """Raised when there's a configuration problem."""

    pass


class TemplateError(ColdMailerError):
    """Raised when there's a template rendering problem."""

    pass


class RecruiterError(ColdMailerError):
    """Raised when there's a recruiter data problem."""

    pass


class RecruiterNotFoundError(RecruiterError):
    """Raised when a recruiter is not found."""

    pass


class DuplicateRecruiterError(RecruiterError):
    """Raised when attempting to add a duplicate recruiter."""

    pass


class EmailError(ColdMailerError):
    """Raised when there's an email sending problem."""

    pass


class SMTPConnectionError(EmailError):
    """Raised when SMTP connection fails."""

    pass


class RateLimitError(ColdMailerError):
    """Raised when rate limit is exceeded."""

    pass


class ValidationError(ColdMailerError):
    """Raised when validation fails."""

    pass


class DataFormatError(ColdMailerError):
    """Raised when there's a data format problem."""

    pass
