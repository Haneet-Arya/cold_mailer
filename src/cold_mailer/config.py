"""Configuration management using Pydantic settings."""

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    """Get the project root directory."""
    current = Path.cwd()
    if (current / "config" / "config.yaml").exists():
        return current
    if (current / "pyproject.toml").exists():
        return current
    return current


class SMTPSettings(BaseModel):
    """SMTP server settings."""

    host: str = "smtp.gmail.com"
    port: int = 587
    use_tls: bool = True
    timeout: int = 30


class RateLimitSettings(BaseModel):
    """Rate limiting settings."""

    emails_per_hour: int = 20
    delay_between_emails: int = 30
    max_emails_per_day: int = 100


class PathSettings(BaseModel):
    """File path settings."""

    templates: str = "templates"
    data: str = "data"
    attachments: str = "attachments"
    logs: str = "logs"


class SenderSettings(BaseModel):
    """Sender information."""

    name: str = "Your Name"
    signature: str = "Best regards,\nYour Name"


class EmailSettings(BaseModel):
    """Email settings."""

    subject_prefix: str = ""
    default_template: str = "default"
    attach_resume: bool = True
    resume_filename: str = "resume.pdf"


class GreetingStyle(BaseModel):
    """Greeting style configuration."""

    with_title: str
    without_title: str


class LoggingSettings(BaseModel):
    """Logging settings."""

    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file: str = "cold_mailer.log"


class AppConfig(BaseModel):
    """Application configuration from YAML."""

    smtp: SMTPSettings = Field(default_factory=SMTPSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    data_format: Literal["csv", "json", "auto"] = "auto"
    paths: PathSettings = Field(default_factory=PathSettings)
    sender: SenderSettings = Field(default_factory=SenderSettings)
    email: EmailSettings = Field(default_factory=EmailSettings)
    greeting_styles: dict[str, GreetingStyle] = Field(default_factory=dict)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)


class EnvSettings(BaseSettings):
    """Environment variable settings."""

    model_config = SettingsConfigDict(
        env_file="../../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gmail_email: str = ""
    gmail_app_password: str = ""


class Config:
    """Main configuration class combining YAML and environment settings."""

    _instance: "Config | None" = None
    _project_root: Path | None = None

    def __init__(self, project_root: Path | None = None):
        self._project_root = project_root or get_project_root()
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML and environment."""
        config_path = self._project_root / "config" / "config.yaml"

        if config_path.exists():
            with open(config_path) as f:
                yaml_config = yaml.safe_load(f) or {}
            self.app = AppConfig(**yaml_config)
        else:
            self.app = AppConfig()

        env_file = self._project_root / ".env"
        if env_file.exists():
            self.env = EnvSettings(_env_file=str(env_file))
        else:
            self.env = EnvSettings()

        self._setup_default_greeting_styles()

    def _setup_default_greeting_styles(self) -> None:
        """Set up default greeting styles if not configured."""
        defaults = {
            "formal": GreetingStyle(
                with_title="Dear {title} {last_name},",
                without_title="Dear {first_name} {last_name},",
            ),
            "semi_formal": GreetingStyle(
                with_title="Dear {title} {last_name},",
                without_title="Dear {first_name},",
            ),
            "casual": GreetingStyle(
                with_title="Hi {first_name},",
                without_title="Hi {first_name},",
            ),
            "professional": GreetingStyle(
                with_title="Hello {title} {last_name},",
                without_title="Hello {first_name},",
            ),
        }
        for style, greeting in defaults.items():
            if style not in self.app.greeting_styles:
                self.app.greeting_styles[style] = greeting

    @property
    def project_root(self) -> Path:
        """Get project root path."""
        return self._project_root

    @property
    def templates_path(self) -> Path:
        """Get templates directory path."""
        return self._project_root / self.app.paths.templates

    @property
    def data_path(self) -> Path:
        """Get data directory path."""
        return self._project_root / self.app.paths.data

    @property
    def attachments_path(self) -> Path:
        """Get attachments directory path."""
        return self._project_root / self.app.paths.attachments

    @property
    def logs_path(self) -> Path:
        """Get logs directory path."""
        return self._project_root / self.app.paths.logs

    @property
    def resume_path(self) -> Path:
        """Get resume file path."""
        return self.attachments_path / self.app.email.resume_filename

    def get_data_format(self) -> Literal["csv", "json"]:
        """Get the data format, auto-detecting if necessary."""
        if self.app.data_format != "auto":
            return self.app.data_format

        json_file = self.data_path / "recruiters.json"
        csv_file = self.data_path / "recruiters.csv"

        if json_file.exists() and not csv_file.exists():
            return "json"
        if csv_file.exists() and not json_file.exists():
            return "csv"
        if json_file.exists() and csv_file.exists():
            json_mtime = json_file.stat().st_mtime
            csv_mtime = csv_file.stat().st_mtime
            return "json" if json_mtime > csv_mtime else "csv"

        return "csv"

    def set_data_format(self, format: Literal["csv", "json"]) -> None:
        """Update data format in config file."""
        config_path = self._project_root / "config" / "config.yaml"

        if config_path.exists():
            with open(config_path) as f:
                yaml_config = yaml.safe_load(f) or {}
        else:
            yaml_config = {}

        yaml_config["data_format"] = format

        with open(config_path, "w") as f:
            yaml.dump(yaml_config, f, default_flow_style=False, sort_keys=False)

        self.app.data_format = format

    def reload(self) -> None:
        """Reload configuration from files."""
        self._load_config()

    @classmethod
    def get_instance(cls, project_root: Path | None = None) -> "Config":
        """Get or create singleton instance."""
        if cls._instance is None or (
            project_root is not None and cls._instance._project_root != project_root
        ):
            cls._instance = cls(project_root)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None


def get_config(project_root: Path | None = None) -> Config:
    """Get configuration instance."""
    return Config.get_instance(project_root)
