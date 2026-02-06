"""SMTP email sending functionality."""

import smtplib
from collections.abc import Callable
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .config import Config, get_config
from .exceptions import EmailError, SMTPConnectionError
from .rate_limiter import RateLimiter
from .recruiter_manager import Recruiter, RecruiterManager
from .template_engine import TemplateEngine


class Mailer:
    """Handles email sending via SMTP."""

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self.template_engine = TemplateEngine(config)
        self.rate_limiter = RateLimiter(config)
        self.recruiter_manager = RecruiterManager(config)

    def test_connection(self) -> tuple[bool, str]:
        """
        Test SMTP connection.

        Returns:
            Tuple of (success, message).
        """
        smtp_config = self.config.app.smtp
        email = self.config.env.gmail_email
        password = self.config.env.gmail_app_password

        if not email:
            return False, "GMAIL_EMAIL not set in .env file"
        if not password:
            return False, "GMAIL_APP_PASSWORD not set in .env file"

        try:
            with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=smtp_config.timeout) as server:
                if smtp_config.use_tls:
                    server.starttls()
                server.login(email, password)
                return True, f"Successfully connected and authenticated as {email}"
        except smtplib.SMTPAuthenticationError:
            return False, "Authentication failed. Check your email and app password."
        except smtplib.SMTPConnectError as e:
            return False, f"Connection failed: {e}"
        except TimeoutError:
            return False, f"Connection timed out after {smtp_config.timeout} seconds"
        except Exception as e:
            return False, f"Connection error: {e}"

    def _create_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachment_path: Path | None = None,
    ) -> MIMEMultipart:
        """Create email message with optional attachment."""
        msg = MIMEMultipart()
        msg["From"] = self.config.env.gmail_email
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", "utf-8"))

        if attachment_path and attachment_path.exists():
            with open(attachment_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=attachment_path.name,
                )
                msg.attach(attachment)

        return msg

    def send_email(
        self,
        recruiter: Recruiter,
        template_name: str,
        custom_vars: dict[str, str] | None = None,
        attach_resume: bool | None = None,
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """
        Send an email to a recruiter.

        Args:
            recruiter: Recruiter to send to.
            template_name: Template to use.
            custom_vars: Additional template variables.
            attach_resume: Whether to attach resume (None = use config default).
            dry_run: If True, don't actually send.

        Returns:
            Tuple of (success, message).
        """
        self.rate_limiter.check_rate_limit()

        subject, body = self.template_engine.render(template_name, recruiter, custom_vars)

        if dry_run:
            preview = self.template_engine.render_preview(template_name, recruiter, custom_vars)
            return True, f"DRY RUN - Would send:\n{preview}"

        if attach_resume is None:
            attach_resume = self.config.app.email.attach_resume

        attachment_path = None
        if attach_resume:
            resume_path = self.config.resume_path
            if resume_path.exists():
                attachment_path = resume_path

        email = self.config.env.gmail_email
        password = self.config.env.gmail_app_password

        if not email or not password:
            raise EmailError("Gmail credentials not configured. Set GMAIL_EMAIL and GMAIL_APP_PASSWORD in .env")

        smtp_config = self.config.app.smtp

        try:
            msg = self._create_message(recruiter.email, subject, body, attachment_path)

            with smtplib.SMTP(smtp_config.host, smtp_config.port, timeout=smtp_config.timeout) as server:
                if smtp_config.use_tls:
                    server.starttls()
                server.login(email, password)
                server.send_message(msg)

            self.rate_limiter.record_sent(
                recruiter_id=recruiter.id,
                email=recruiter.email,
                template=template_name,
                subject=subject,
            )

            self.recruiter_manager.mark_sent(recruiter.id)

            return True, f"Email sent successfully to {recruiter.email}"

        except smtplib.SMTPAuthenticationError:
            raise SMTPConnectionError("Authentication failed. Check your credentials.")
        except smtplib.SMTPRecipientsRefused:
            raise EmailError(f"Recipient refused: {recruiter.email}")
        except smtplib.SMTPException as e:
            raise EmailError(f"SMTP error: {e}")
        except Exception as e:
            raise EmailError(f"Failed to send email: {e}")

    def send_to_all_pending(
        self,
        template_name: str | None = None,
        custom_vars: dict[str, str] | None = None,
        dry_run: bool = False,
        progress_callback: Callable | None = None,
    ) -> dict:
        """
        Send emails to all pending recruiters.

        Args:
            template_name: Template to use (None = default).
            custom_vars: Additional template variables.
            dry_run: If True, don't actually send.
            progress_callback: Callback function for progress updates.

        Returns:
            Results dictionary with sent, failed, and skipped counts.
        """
        if template_name is None:
            template_name = self.config.app.email.default_template

        pending = self.recruiter_manager.get_pending()

        results = {
            "total": len(pending),
            "sent": 0,
            "failed": 0,
            "skipped": 0,
            "errors": [],
        }

        for i, recruiter in enumerate(pending):
            if progress_callback:
                progress_callback(i + 1, len(pending), recruiter)

            can_send, reason = self.rate_limiter.can_send()
            if not can_send:
                results["skipped"] += 1
                results["errors"].append({
                    "email": recruiter.email,
                    "error": f"Rate limit: {reason}",
                })
                continue

            try:
                success, message = self.send_email(
                    recruiter,
                    template_name,
                    custom_vars,
                    dry_run=dry_run,
                )
                if success:
                    results["sent"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "email": recruiter.email,
                        "error": message,
                    })
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "email": recruiter.email,
                    "error": str(e),
                })

            if not dry_run and i < len(pending) - 1:
                self.rate_limiter.wait_for_delay()

        return results

    def preview_email(
        self,
        recruiter: Recruiter,
        template_name: str,
        custom_vars: dict[str, str] | None = None,
    ) -> str:
        """Generate a preview of an email."""
        return self.template_engine.render_preview(template_name, recruiter, custom_vars)
