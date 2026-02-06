"""Input validation utilities."""

import re
from typing import Literal

from email_validator import EmailNotValidError, validate_email

from .exceptions import ValidationError


def validate_email_address(email: str) -> str:
    """
    Validate an email address.

    Args:
        email: Email address to validate.

    Returns:
        Normalized email address.

    Raises:
        ValidationError: If email is invalid.
    """
    try:
        result = validate_email(email, check_deliverability=False)
        return result.normalized
    except EmailNotValidError as e:
        raise ValidationError(f"Invalid email address '{email}': {e}")


def validate_recruiter_status(status: str) -> Literal["pending", "sent", "replied", "bounced"]:
    """
    Validate recruiter status.

    Args:
        status: Status to validate.

    Returns:
        Validated status.

    Raises:
        ValidationError: If status is invalid.
    """
    valid_statuses = {"pending", "sent", "replied", "bounced"}
    status_lower = status.lower().strip()
    if status_lower not in valid_statuses:
        raise ValidationError(
            f"Invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}"
        )
    return status_lower


def validate_greeting_style(
    style: str,
) -> Literal["formal", "semi_formal", "casual", "professional"]:
    """
    Validate greeting style.

    Args:
        style: Style to validate.

    Returns:
        Validated style.

    Raises:
        ValidationError: If style is invalid.
    """
    valid_styles = {"formal", "semi_formal", "casual", "professional"}
    style_lower = style.lower().strip()
    if style_lower not in valid_styles:
        raise ValidationError(
            f"Invalid greeting style '{style}'. Must be one of: {', '.join(sorted(valid_styles))}"
        )
    return style_lower


def validate_data_format(format: str) -> Literal["csv", "json"]:
    """
    Validate data format.

    Args:
        format: Format to validate.

    Returns:
        Validated format.

    Raises:
        ValidationError: If format is invalid.
    """
    valid_formats = {"csv", "json"}
    format_lower = format.lower().strip()
    if format_lower not in valid_formats:
        raise ValidationError(
            f"Invalid data format '{format}'. Must be one of: {', '.join(sorted(valid_formats))}"
        )
    return format_lower


def validate_name(name: str, field_name: str = "Name") -> str:
    """
    Validate a name field.

    Args:
        name: Name to validate.
        field_name: Field name for error messages.

    Returns:
        Stripped name.

    Raises:
        ValidationError: If name is empty or invalid.
    """
    name = name.strip()
    if not name:
        raise ValidationError(f"{field_name} cannot be empty")
    if len(name) > 100:
        raise ValidationError(f"{field_name} is too long (max 100 characters)")
    return name


def validate_company(company: str) -> str:
    """
    Validate company name.

    Args:
        company: Company name to validate.

    Returns:
        Stripped company name.

    Raises:
        ValidationError: If company name is empty or invalid.
    """
    company = company.strip()
    if not company:
        raise ValidationError("Company name cannot be empty")
    if len(company) > 200:
        raise ValidationError("Company name is too long (max 200 characters)")
    return company


def validate_title(title: str | None) -> str | None:
    """
    Validate honorific title.

    Args:
        title: Title to validate.

    Returns:
        Validated title or None.

    Raises:
        ValidationError: If title is invalid.
    """
    if not title:
        return None

    title = title.strip()
    valid_titles = {"Mr.", "Ms.", "Mrs.", "Dr.", "Prof.", ""}
    if title not in valid_titles:
        raise ValidationError(
            f"Invalid title '{title}'. Must be one of: {', '.join(t for t in sorted(valid_titles) if t)}"
        )
    return title if title else None


def validate_custom_field_key(key: str) -> str:
    """
    Validate a custom field key.

    Args:
        key: Key to validate.

    Returns:
        Validated key.

    Raises:
        ValidationError: If key is invalid.
    """
    key = key.strip()
    if not key:
        raise ValidationError("Custom field key cannot be empty")
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
        raise ValidationError(
            f"Invalid custom field key '{key}'. "
            "Must start with letter or underscore and contain only alphanumeric characters and underscores"
        )
    if len(key) > 50:
        raise ValidationError("Custom field key is too long (max 50 characters)")
    return key


def parse_custom_fields(custom_str: str) -> dict[str, str]:
    """
    Parse custom fields from string format (key=value,key2=value2).

    Args:
        custom_str: String with custom fields.

    Returns:
        Dictionary of custom fields.

    Raises:
        ValidationError: If format is invalid.
    """
    if not custom_str:
        return {}

    result = {}
    pairs = custom_str.split(",")

    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue

        if "=" not in pair:
            raise ValidationError(
                f"Invalid custom field format: '{pair}'. Expected 'key=value' format"
            )

        key, value = pair.split("=", 1)
        key = validate_custom_field_key(key)
        result[key] = value.strip()

    return result


def validate_template_name(name: str) -> str:
    """
    Validate template name.

    Args:
        name: Template name to validate.

    Returns:
        Validated template name.

    Raises:
        ValidationError: If name is invalid.
    """
    name = name.strip()
    if not name:
        raise ValidationError("Template name cannot be empty")
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValidationError(
            f"Invalid template name '{name}'. "
            "Must contain only alphanumeric characters, underscores, and hyphens"
        )
    if len(name) > 50:
        raise ValidationError("Template name is too long (max 50 characters)")
    return name
