# Cold Mailer CLI

A Python CLI application for sending personalized cold emails to recruiters with template support, CSV/JSON-based recruiter management, and Gmail SMTP integration.

## Features

- **Template Personalization**: Jinja2 templates with recruiter name, company, job title, and custom fields
- **Dual Data Format**: Store recruiters in CSV (spreadsheet-friendly) or JSON (nested custom fields)
- **Rate Limiting**: Prevents Gmail spam detection (configurable hourly/daily limits with delays)
- **Greeting Styles**: Formal, semi-formal, casual, or professional greetings
- **PDF Attachment**: Auto-attach resume to all emails
- **Dry Run Mode**: Preview emails before sending
- **Status Tracking**: Track recruiters as pending/sent/replied/bounced

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd cold_mailer

# Create virtual environment and install
uv venv
uv pip install -e .
```

## Quick Start

```bash
# 1. Initialize project structure
cold-mailer init

# 2. Configure credentials
cp .env.example .env
# Edit .env with your Gmail email and app password

# 3. Configure config/config.yaml and set sender name/signature
cp config/config.example.yaml config/config.yaml

# 4. Test SMTP connection
cold-mailer config test-smtp

# 5. Add recruiters
cold-mailer add recruiter

# 6. Preview an email
cold-mailer send to -r recruiter@company.com --dry-run

# 7. Send to all pending recruiters
cold-mailer send all
```

## Gmail Setup

1. Enable 2-Factor Authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate a new app password for "Mail"
4. Add credentials to `.env`:

```bash
GMAIL_EMAIL=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

## CLI Commands

### Sending Emails

```bash
# Send to all pending recruiters
cold-mailer send all

# Send to specific recruiter
cold-mailer send to -r email@company.com

# Use specific template
cold-mailer send to -r email@company.com -t follow_up

# Add custom variables
cold-mailer send to -r email@company.com --custom referral=John,notes=Met at conference

# Preview without sending
cold-mailer send all --dry-run
```

### Managing Recruiters

```bash
# List all recruiters
cold-mailer list recruiters

# List by status
cold-mailer list recruiters --status pending

# Add recruiter interactively
cold-mailer add recruiter
```

### Templates

```bash
# List available templates
cold-mailer list templates
```

Built-in templates:
- `default` - Standard cold email
- `follow_up` - Follow-up email
- `referral` - Referral-based introduction

### Configuration

```bash
# Test SMTP connection
cold-mailer config test-smtp

# Switch data format
cold-mailer config set data_format json

# Convert between formats
cold-mailer convert --to json
```

### Status

```bash
# View statistics and rate limit status
cold-mailer status
```

## Data Formats

### CSV Format

```csv
id,email,first_name,last_name,title,company,job_title,greeting_style,custom_field_1,custom_field_2,status,last_contacted
1,john@company.com,John,Smith,Mr.,Acme Corp,Software Engineer,semi_formal,skills=Python,referral=Jane,pending,
```

### JSON Format

```json
{
  "recruiters": [
    {
      "id": "1",
      "email": "john@company.com",
      "first_name": "John",
      "last_name": "Smith",
      "title": "Mr.",
      "company": "Acme Corp",
      "job_title": "Software Engineer",
      "greeting_style": "semi_formal",
      "custom_fields": {
        "skills": "Python, React",
        "referral": "Jane Doe"
      },
      "status": "pending",
      "last_contacted": null
    }
  ]
}
```

## Template Variables

Available in Jinja2 templates:

| Variable | Description |
|----------|-------------|
| `{{ greeting }}` | Auto-generated greeting based on style |
| `{{ recruiter.first_name }}` | Recruiter's first name |
| `{{ recruiter.last_name }}` | Recruiter's last name |
| `{{ recruiter.company }}` | Company name |
| `{{ recruiter.job_title }}` | Position applying for |
| `{{ sender.name }}` | Your name (from config) |
| `{{ sender.signature }}` | Your signature (from config) |
| `{{ custom.* }}` | Custom fields from recruiter data |

## Configuration

Edit `config/config.yaml`:

```yaml
# Rate limiting
rate_limit:
  emails_per_hour: 20
  delay_between_emails: 30  # seconds
  max_emails_per_day: 100

# Sender info
sender:
  name: "Your Name"
  signature: |
    Best regards,
    Your Name
    your.email@gmail.com

# Email settings
email:
  default_template: default
  attach_resume: true
  resume_filename: resume.pdf
```

## Project Structure

```
cold_mailer/
├── src/cold_mailer/        # Source code
├── templates/              # Jinja2 email templates
├── data/                   # Recruiter data & sent log
├── config/                 # config.yaml
├── attachments/            # Resume storage
└── logs/                   # Application logs
```

## License

MIT
