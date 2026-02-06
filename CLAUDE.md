# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Development Commands

```bash
# Install dependencies (uses uv)
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"

# Run CLI
cold-mailer --help

# Run specific commands
cold-mailer init                    # Initialize project structure
cold-mailer list templates          # List email templates
cold-mailer list recruiters         # List all recruiters
cold-mailer send to -r EMAIL --dry-run  # Preview email
cold-mailer config test-smtp        # Test SMTP connection
```

## Architecture

This is a CLI application for sending personalized cold emails to recruiters. It uses Click for CLI, Jinja2 for templates, and Pydantic for configuration.

### Core Flow

1. **CLI (`cli.py`)** → Entry point, parses commands, orchestrates operations
2. **Mailer (`mailer.py`)** → Sends emails via SMTP, coordinates template rendering and rate limiting
3. **RecruiterManager (`recruiter_manager.py`)** → CRUD operations for recruiter data (CSV/JSON)
4. **TemplateEngine (`template_engine.py`)** → Renders Jinja2 templates with recruiter context
5. **RateLimiter (`rate_limiter.py`)** → Tracks sent emails, enforces hourly/daily limits

### Configuration System

- **`config/config.yaml`** → Application settings (SMTP, rate limits, paths, sender info)
- **`.env`** → Gmail credentials (GMAIL_EMAIL, GMAIL_APP_PASSWORD)
- **`Config` class (`config.py`)** → Combines YAML config with environment variables via Pydantic

### Data Storage

Supports both CSV and JSON formats with auto-detection:
- CSV: `data/recruiters.csv` - spreadsheet-friendly, flat structure
- JSON: `data/recruiters.json` - supports nested custom_fields

The `data_format` setting in config.yaml controls which format is used (csv/json/auto).

### Template Variables

Templates receive this context:
- `greeting` - Auto-generated based on recruiter's greeting_style
- `recruiter.*` - email, first_name, last_name, company, job_title, etc.
- `sender.*` - name, signature (from config)
- `job.*` - title, department
- `custom.*` - Custom fields from recruiter data

### Rate Limiting

Tracks sent emails in `data/sent_log.json`. Configurable limits:
- `emails_per_hour` (default: 20)
- `delay_between_emails` (default: 30 seconds)
- `max_emails_per_day` (default: 100)
