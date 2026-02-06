"""Jinja2 template engine for email rendering."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, UndefinedError

from .config import Config, get_config
from .exceptions import TemplateError
from .recruiter_manager import Recruiter


class TemplateEngine:
    """Handles email template rendering with Jinja2."""

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._env: Environment | None = None

    @property
    def env(self) -> Environment:
        """Get or create Jinja2 environment."""
        if self._env is None:
            templates_path = self.config.templates_path
            if not templates_path.exists():
                templates_path.mkdir(parents=True, exist_ok=True)

            self._env = Environment(
                loader=FileSystemLoader(str(templates_path)),
                autoescape=False,
                trim_blocks=True,
                lstrip_blocks=True,
            )
        return self._env

    def list_templates(self) -> list[str]:
        """List all available templates."""
        templates_path = self.config.templates_path
        if not templates_path.exists():
            return []

        templates = []
        for file in templates_path.glob("*.j2"):
            templates.append(file.stem)
        return sorted(templates)

    def template_exists(self, name: str) -> bool:
        """Check if a template exists."""
        template_file = self.config.templates_path / f"{name}.j2"
        return template_file.exists()

    def get_template_path(self, name: str) -> Path:
        """Get path to a template file."""
        return self.config.templates_path / f"{name}.j2"

    def _generate_greeting(self, recruiter: Recruiter) -> str:
        """Generate greeting based on recruiter's greeting style."""
        style = recruiter.greeting_style
        greeting_config = self.config.app.greeting_styles.get(style)

        if not greeting_config:
            greeting_config = self.config.app.greeting_styles.get("semi_formal")

        if recruiter.title and greeting_config:
            template_str = greeting_config.with_title
        elif greeting_config:
            template_str = greeting_config.without_title
        else:
            template_str = "Hi {first_name},"

        return template_str.format(
            title=recruiter.title or "",
            first_name=recruiter.first_name,
            last_name=recruiter.last_name,
        ).strip()

    def _build_context(
        self,
        recruiter: Recruiter,
        custom_vars: dict[str, str] | None = None,
    ) -> dict:
        """Build template context from recruiter and custom variables."""
        greeting = self._generate_greeting(recruiter)

        context = {
            "greeting": greeting,
            "recruiter": {
                "email": recruiter.email,
                "first_name": recruiter.first_name,
                "last_name": recruiter.last_name,
                "full_name": recruiter.get_full_name(),
                "title": recruiter.title or "",
                "company": recruiter.company,
                "job_title": recruiter.job_title,
                "department": recruiter.department,
            },
            "sender": {
                "name": self.config.app.sender.name,
                "signature": self.config.app.sender.signature,
            },
            "job": {
                "title": recruiter.job_title,
                "department": recruiter.department,
            },
            "custom": {},
        }

        for key, value in recruiter.custom_fields.items():
            context["custom"][key] = value

        if custom_vars:
            for key, value in custom_vars.items():
                context["custom"][key] = value

        return context

    def render(
        self,
        template_name: str,
        recruiter: Recruiter,
        custom_vars: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        """
        Render an email template.

        Args:
            template_name: Name of the template (without .j2 extension).
            recruiter: Recruiter to render for.
            custom_vars: Additional custom variables.

        Returns:
            Tuple of (subject, body).

        Raises:
            TemplateError: If template not found or rendering fails.
        """
        if not self.template_exists(template_name):
            raise TemplateError(f"Template '{template_name}' not found")

        try:
            template = self.env.get_template(f"{template_name}.j2")
            context = self._build_context(recruiter, custom_vars)
            rendered = template.render(**context)

            lines = rendered.strip().split("\n", 1)
            if len(lines) < 2:
                raise TemplateError(
                    f"Template '{template_name}' must have a subject line followed by body"
                )

            subject = lines[0].strip()
            if subject.lower().startswith("subject:"):
                subject = subject[8:].strip()

            body = lines[1].strip()

            if self.config.app.email.subject_prefix:
                subject = f"{self.config.app.email.subject_prefix} {subject}"

            return subject, body

        except TemplateNotFound:
            raise TemplateError(f"Template '{template_name}' not found")
        except UndefinedError as e:
            raise TemplateError(f"Template variable error: {e}")
        except Exception as e:
            raise TemplateError(f"Error rendering template '{template_name}': {e}")

    def render_preview(
        self,
        template_name: str,
        recruiter: Recruiter,
        custom_vars: dict[str, str] | None = None,
    ) -> str:
        """
        Render a preview of the email.

        Args:
            template_name: Name of the template.
            recruiter: Recruiter to render for.
            custom_vars: Additional custom variables.

        Returns:
            Formatted preview string.
        """
        subject, body = self.render(template_name, recruiter, custom_vars)

        preview = f"""
{'='*60}
To: {recruiter.email}
Subject: {subject}
{'='*60}

{body}

{'='*60}
"""
        return preview.strip()

    def get_template_variables(self, template_name: str) -> list[str]:
        """
        Extract variable names used in a template.

        Args:
            template_name: Name of the template.

        Returns:
            List of variable names.
        """
        if not self.template_exists(template_name):
            raise TemplateError(f"Template '{template_name}' not found")

        template_path = self.get_template_path(template_name)
        content = template_path.read_text()

        from jinja2 import meta

        ast = self.env.parse(content)
        variables = meta.find_undeclared_variables(ast)
        return sorted(variables)


def create_default_templates(templates_path: Path) -> None:
    """Create default email templates."""
    templates_path.mkdir(parents=True, exist_ok=True)

    default_template = """Subject: Application for {{ job.title or "Software Engineer" }} Position at {{ recruiter.company }}

{{ greeting }}

I hope this email finds you well. I am writing to express my strong interest in the {{ job.title or "Software Engineer" }} position at {{ recruiter.company }}.

With my background in software development and passion for building impactful solutions, I believe I would be a great fit for your team. I am particularly excited about the opportunity to contribute to {{ recruiter.company }}'s mission and growth.

I have attached my resume for your review and would welcome the opportunity to discuss how my skills and experience align with your team's needs.

Thank you for your time and consideration. I look forward to hearing from you.

{{ sender.signature }}
"""

    follow_up_template = """Subject: Following Up - {{ job.title or "Software Engineer" }} Application at {{ recruiter.company }}

{{ greeting }}

I wanted to follow up on my previous application for the {{ job.title or "Software Engineer" }} position at {{ recruiter.company }}.

I remain very interested in the opportunity and would love to learn more about the role and how I might contribute to your team.

{% if custom.previous_contact %}
Since we last spoke{{ custom.previous_contact }}, I have continued to develop my skills and remain enthusiastic about the possibility of joining {{ recruiter.company }}.
{% endif %}

Please let me know if you need any additional information from me. I am happy to provide references or schedule a call at your convenience.

Thank you again for considering my application.

{{ sender.signature }}
"""

    referral_template = """Subject: {{ custom.referral or "Referral" }} Recommended I Reach Out - {{ job.title or "Software Engineer" }} at {{ recruiter.company }}

{{ greeting }}

{% if custom.referral %}
{{ custom.referral }} suggested I reach out to you regarding the {{ job.title or "Software Engineer" }} position at {{ recruiter.company }}.
{% else %}
I was referred to you regarding the {{ job.title or "Software Engineer" }} position at {{ recruiter.company }}.
{% endif %}

{% if custom.connection %}
{{ custom.connection }}
{% endif %}

I am excited about the opportunity to bring my skills and experience to your team. {{ recruiter.company }}'s work in {{ recruiter.department or "technology" }} aligns perfectly with my professional interests and career goals.

I have attached my resume for your review. I would greatly appreciate the opportunity to discuss how I can contribute to your team.

Thank you for your time and consideration.

{{ sender.signature }}
"""

    (templates_path / "default.j2").write_text(default_template)
    (templates_path / "follow_up.j2").write_text(follow_up_template)
    (templates_path / "referral.j2").write_text(referral_template)
