"""Rate limiting for email sending."""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config, get_config
from .exceptions import RateLimitError


class RateLimiter:
    """Handles rate limiting for email sending."""

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._sent_log_path = self.config.data_path / "sent_log.json"
        self._sent_emails: list[dict] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Ensure sent log is loaded."""
        if not self._loaded:
            self._load_sent_log()

    def _load_sent_log(self) -> None:
        """Load sent email log from file."""
        self._sent_emails = []

        if self._sent_log_path.exists():
            try:
                with open(self._sent_log_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self._sent_emails = data.get("sent_emails", [])
            except (json.JSONDecodeError, Exception):
                self._sent_emails = []

        self._loaded = True

    def _save_sent_log(self) -> None:
        """Save sent email log to file."""
        self.config.data_path.mkdir(parents=True, exist_ok=True)

        data = {"sent_emails": self._sent_emails}

        with open(self._sent_log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _get_emails_in_window(self, window: timedelta) -> list[dict]:
        """Get emails sent within a time window."""
        self._ensure_loaded()
        cutoff = datetime.now() - window

        return [
            email
            for email in self._sent_emails
            if datetime.fromisoformat(email["timestamp"]) > cutoff
        ]

    def get_emails_last_hour(self) -> int:
        """Get count of emails sent in the last hour."""
        return len(self._get_emails_in_window(timedelta(hours=1)))

    def get_emails_today(self) -> int:
        """Get count of emails sent today."""
        self._ensure_loaded()
        today = datetime.now().date()

        return len(
            [
                email
                for email in self._sent_emails
                if datetime.fromisoformat(email["timestamp"]).date() == today
            ]
        )

    def can_send(self) -> tuple[bool, str]:
        """
        Check if an email can be sent within rate limits.

        Returns:
            Tuple of (can_send, reason).
        """
        hourly_limit = self.config.app.rate_limit.emails_per_hour
        daily_limit = self.config.app.rate_limit.max_emails_per_day

        emails_last_hour = self.get_emails_last_hour()
        emails_today = self.get_emails_today()

        if emails_today >= daily_limit:
            return False, f"Daily limit reached ({emails_today}/{daily_limit})"

        if emails_last_hour >= hourly_limit:
            return False, f"Hourly limit reached ({emails_last_hour}/{hourly_limit})"

        return True, "OK"

    def check_rate_limit(self) -> None:
        """
        Check rate limit and raise exception if exceeded.

        Raises:
            RateLimitError: If rate limit is exceeded.
        """
        can_send, reason = self.can_send()
        if not can_send:
            raise RateLimitError(f"Rate limit exceeded: {reason}")

    def record_sent(
        self,
        recruiter_id: str,
        email: str,
        template: str,
        subject: str,
    ) -> None:
        """
        Record a sent email.

        Args:
            recruiter_id: ID of the recruiter.
            email: Email address sent to.
            template: Template name used.
            subject: Email subject.
        """
        self._ensure_loaded()

        record = {
            "timestamp": datetime.now().isoformat(),
            "recruiter_id": recruiter_id,
            "email": email,
            "template": template,
            "subject": subject,
        }

        self._sent_emails.append(record)
        self._save_sent_log()

    def wait_for_delay(self) -> None:
        """Wait for the configured delay between emails."""
        delay = self.config.app.rate_limit.delay_between_emails
        if delay > 0:
            time.sleep(delay)

    def get_wait_time(self) -> int:
        """
        Get seconds to wait before next email can be sent.

        Returns:
            Seconds to wait (0 if no wait needed).
        """
        hourly_limit = self.config.app.rate_limit.emails_per_hour
        daily_limit = self.config.app.rate_limit.max_emails_per_day

        emails_today = self.get_emails_today()
        if emails_today >= daily_limit:
            tomorrow = datetime.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
            return int((tomorrow - datetime.now()).total_seconds())

        emails_last_hour = self.get_emails_last_hour()
        if emails_last_hour >= hourly_limit:
            hour_ago = datetime.now() - timedelta(hours=1)
            oldest_in_window = min(
                (
                    datetime.fromisoformat(e["timestamp"])
                    for e in self._get_emails_in_window(timedelta(hours=1))
                ),
                default=datetime.now(),
            )
            wait_until = oldest_in_window + timedelta(hours=1)
            return max(0, int((wait_until - datetime.now()).total_seconds()))

        return 0

    def get_statistics(self) -> dict:
        """Get rate limiting statistics."""
        self._ensure_loaded()

        hourly_limit = self.config.app.rate_limit.emails_per_hour
        daily_limit = self.config.app.rate_limit.max_emails_per_day

        emails_last_hour = self.get_emails_last_hour()
        emails_today = self.get_emails_today()

        return {
            "emails_last_hour": emails_last_hour,
            "hourly_limit": hourly_limit,
            "hourly_remaining": max(0, hourly_limit - emails_last_hour),
            "emails_today": emails_today,
            "daily_limit": daily_limit,
            "daily_remaining": max(0, daily_limit - emails_today),
            "total_sent": len(self._sent_emails),
            "delay_between_emails": self.config.app.rate_limit.delay_between_emails,
        }

    def get_sent_history(self, limit: int = 10) -> list[dict]:
        """Get recent sent email history."""
        self._ensure_loaded()
        return sorted(
            self._sent_emails,
            key=lambda x: x["timestamp"],
            reverse=True,
        )[:limit]

    def clear_history(self) -> None:
        """Clear sent email history."""
        self._sent_emails = []
        self._save_sent_log()
        self._loaded = True
