"""Recruiter data management with CSV and JSON support."""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .config import Config, get_config
from .exceptions import (
    DataFormatError,
    DuplicateRecruiterError,
    RecruiterError,
    RecruiterNotFoundError,
)
from .validators import (
    validate_company,
    validate_email_address,
    validate_greeting_style,
    validate_name,
    validate_recruiter_status,
    validate_title,
)


class Recruiter(BaseModel):
    """Recruiter data model."""

    id: str
    email: str
    first_name: str
    last_name: str = ""
    title: str | None = None
    company: str
    job_title: str = ""
    department: str = ""
    greeting_style: Literal["formal", "semi_formal", "casual", "professional"] = "semi_formal"
    custom_fields: dict[str, str] = Field(default_factory=dict)
    status: Literal["pending", "sent", "replied", "bounced"] = "pending"
    last_contacted: datetime | None = None

    def get_full_name(self) -> str:
        """Get recruiter's full name."""
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    def to_csv_row(self) -> dict[str, str]:
        """Convert to CSV row format."""
        row = {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "title": self.title or "",
            "company": self.company,
            "job_title": self.job_title,
            "greeting_style": self.greeting_style,
            "status": self.status,
            "last_contacted": self.last_contacted.isoformat() if self.last_contacted else "",
        }
        for i, (key, value) in enumerate(self.custom_fields.items(), 1):
            row[f"custom_field_{i}"] = f"{key}={value}"
        return row

    def to_json_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "title": self.title,
            "company": self.company,
            "job_title": self.job_title,
            "department": self.department,
            "greeting_style": self.greeting_style,
            "custom_fields": self.custom_fields,
            "status": self.status,
            "last_contacted": self.last_contacted.isoformat() if self.last_contacted else None,
        }

    @classmethod
    def from_csv_row(cls, row: dict[str, str]) -> "Recruiter":
        """Create Recruiter from CSV row."""
        custom_fields = {}
        for key, value in row.items():
            if key and key.startswith("custom_field_") and value:
                if "=" in value:
                    field_key, field_value = value.split("=", 1)
                    custom_fields[field_key.strip()] = field_value.strip()

        last_contacted = None
        if row.get("last_contacted"):
            try:
                last_contacted = datetime.fromisoformat(row["last_contacted"])
            except ValueError:
                pass

        return cls(
            id=row.get("id", ""),
            email=row.get("email", ""),
            first_name=row.get("first_name", ""),
            last_name=row.get("last_name", ""),
            title=row.get("title") or None,
            company=row.get("company", ""),
            job_title=row.get("job_title", ""),
            greeting_style=row.get("greeting_style", "semi_formal") or "semi_formal",
            custom_fields=custom_fields,
            status=row.get("status", "pending") or "pending",
            last_contacted=last_contacted,
        )

    @classmethod
    def from_json_dict(cls, data: dict) -> "Recruiter":
        """Create Recruiter from JSON dictionary."""
        last_contacted = None
        if data.get("last_contacted"):
            try:
                last_contacted = datetime.fromisoformat(data["last_contacted"])
            except ValueError:
                pass

        return cls(
            id=data.get("id", ""),
            email=data.get("email", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            title=data.get("title"),
            company=data.get("company", ""),
            job_title=data.get("job_title", ""),
            department=data.get("department", ""),
            greeting_style=data.get("greeting_style", "semi_formal") or "semi_formal",
            custom_fields=data.get("custom_fields", {}),
            status=data.get("status", "pending") or "pending",
            last_contacted=last_contacted,
        )


class RecruiterManager:
    """Manages recruiter data with CSV and JSON support."""

    CSV_HEADERS = [
        "id",
        "email",
        "first_name",
        "last_name",
        "title",
        "company",
        "job_title",
        "greeting_style",
        "custom_field_1",
        "custom_field_2",
        "status",
        "last_contacted",
    ]

    def __init__(self, config: Config | None = None):
        self.config = config or get_config()
        self._recruiters: dict[str, Recruiter] = {}
        self._loaded = False

    @property
    def data_format(self) -> Literal["csv", "json"]:
        """Get current data format."""
        return self.config.get_data_format()

    @property
    def csv_path(self) -> Path:
        """Get CSV file path."""
        return self.config.data_path / "recruiters.csv"

    @property
    def json_path(self) -> Path:
        """Get JSON file path."""
        return self.config.data_path / "recruiters.json"

    @property
    def data_path(self) -> Path:
        """Get current data file path based on format."""
        if self.data_format == "json":
            return self.json_path
        return self.csv_path

    def _ensure_loaded(self) -> None:
        """Ensure data is loaded."""
        if not self._loaded:
            self.load()

    def load(self) -> None:
        """Load recruiters from data file."""
        self._recruiters = {}

        if self.data_format == "json":
            self._load_json()
        else:
            self._load_csv()

        self._loaded = True

    def _load_csv(self) -> None:
        """Load recruiters from CSV file."""
        if not self.csv_path.exists():
            return

        try:
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("id") and row.get("email"):
                        recruiter = Recruiter.from_csv_row(row)
                        self._recruiters[recruiter.id] = recruiter
        except Exception as e:
            raise DataFormatError(f"Error loading CSV file: {e}")

    def _load_json(self) -> None:
        """Load recruiters from JSON file."""
        if not self.json_path.exists():
            return

        try:
            with open(self.json_path, encoding="utf-8") as f:
                data = json.load(f)

            recruiters_list = data.get("recruiters", [])
            for item in recruiters_list:
                if item.get("id") and item.get("email"):
                    recruiter = Recruiter.from_json_dict(item)
                    self._recruiters[recruiter.id] = recruiter
        except json.JSONDecodeError as e:
            raise DataFormatError(f"Error parsing JSON file: {e}")
        except Exception as e:
            raise DataFormatError(f"Error loading JSON file: {e}")

    def save(self) -> None:
        """Save recruiters to data file."""
        self.config.data_path.mkdir(parents=True, exist_ok=True)

        if self.data_format == "json":
            self._save_json()
        else:
            self._save_csv()

    def _save_csv(self) -> None:
        """Save recruiters to CSV file."""
        max_custom_fields = max(
            (len(r.custom_fields) for r in self._recruiters.values()), default=2
        )
        max_custom_fields = max(max_custom_fields, 2)

        headers = self.CSV_HEADERS.copy()
        for i in range(3, max_custom_fields + 1):
            if f"custom_field_{i}" not in headers:
                headers.insert(-2, f"custom_field_{i}")

        try:
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=headers, extrasaction="ignore", quoting=csv.QUOTE_MINIMAL
                )
                writer.writeheader()
                for recruiter in sorted(self._recruiters.values(), key=lambda r: r.id):
                    writer.writerow(recruiter.to_csv_row())
        except Exception as e:
            raise DataFormatError(f"Error saving CSV file: {e}")

    def _save_json(self) -> None:
        """Save recruiters to JSON file."""
        data = {
            "recruiters": [
                r.to_json_dict() for r in sorted(self._recruiters.values(), key=lambda r: r.id)
            ]
        }

        try:
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise DataFormatError(f"Error saving JSON file: {e}")

    def get_all(self) -> list[Recruiter]:
        """Get all recruiters."""
        self._ensure_loaded()
        return list(self._recruiters.values())

    def get_by_id(self, id: str) -> Recruiter:
        """Get recruiter by ID."""
        self._ensure_loaded()
        if id not in self._recruiters:
            raise RecruiterNotFoundError(f"Recruiter with ID '{id}' not found")
        return self._recruiters[id]

    def get_by_email(self, email: str) -> Recruiter:
        """Get recruiter by email."""
        self._ensure_loaded()
        email_normalized = email.lower().strip()
        for recruiter in self._recruiters.values():
            if recruiter.email.lower() == email_normalized:
                return recruiter
        raise RecruiterNotFoundError(f"Recruiter with email '{email}' not found")

    def get_by_status(
        self, status: Literal["pending", "sent", "replied", "bounced"]
    ) -> list[Recruiter]:
        """Get recruiters by status."""
        self._ensure_loaded()
        return [r for r in self._recruiters.values() if r.status == status]

    def get_pending(self) -> list[Recruiter]:
        """Get all pending recruiters."""
        return self.get_by_status("pending")

    def add(
        self,
        email: str,
        first_name: str,
        company: str,
        last_name: str = "",
        title: str | None = None,
        job_title: str = "",
        department: str = "",
        greeting_style: str = "semi_formal",
        custom_fields: dict[str, str] | None = None,
    ) -> Recruiter:
        """Add a new recruiter."""
        self._ensure_loaded()

        email = validate_email_address(email)
        first_name = validate_name(first_name, "First name")
        company = validate_company(company)
        if last_name:
            last_name = validate_name(last_name, "Last name")
        if title:
            title = validate_title(title)
        greeting_style = validate_greeting_style(greeting_style)

        for recruiter in self._recruiters.values():
            if recruiter.email.lower() == email.lower():
                raise DuplicateRecruiterError(f"Recruiter with email '{email}' already exists")

        new_id = str(max((int(r.id) for r in self._recruiters.values()), default=0) + 1)

        recruiter = Recruiter(
            id=new_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            title=title,
            company=company,
            job_title=job_title,
            department=department,
            greeting_style=greeting_style,
            custom_fields=custom_fields or {},
            status="pending",
        )

        self._recruiters[new_id] = recruiter
        self.save()
        return recruiter

    def update(self, id: str, **kwargs) -> Recruiter:
        """Update a recruiter."""
        self._ensure_loaded()
        recruiter = self.get_by_id(id)

        if "email" in kwargs:
            kwargs["email"] = validate_email_address(kwargs["email"])
        if "first_name" in kwargs:
            kwargs["first_name"] = validate_name(kwargs["first_name"], "First name")
        if "last_name" in kwargs and kwargs["last_name"]:
            kwargs["last_name"] = validate_name(kwargs["last_name"], "Last name")
        if "company" in kwargs:
            kwargs["company"] = validate_company(kwargs["company"])
        if "title" in kwargs:
            kwargs["title"] = validate_title(kwargs["title"])
        if "greeting_style" in kwargs:
            kwargs["greeting_style"] = validate_greeting_style(kwargs["greeting_style"])
        if "status" in kwargs:
            kwargs["status"] = validate_recruiter_status(kwargs["status"])

        for key, value in kwargs.items():
            if hasattr(recruiter, key):
                setattr(recruiter, key, value)

        self.save()
        return recruiter

    def update_status(
        self, id: str, status: Literal["pending", "sent", "replied", "bounced"]
    ) -> Recruiter:
        """Update recruiter status."""
        status = validate_recruiter_status(status)
        return self.update(id, status=status)

    def mark_sent(self, id: str) -> Recruiter:
        """Mark recruiter as sent and update last_contacted."""
        return self.update(id, status="sent", last_contacted=datetime.now())

    def delete(self, id: str) -> None:
        """Delete a recruiter."""
        self._ensure_loaded()
        if id not in self._recruiters:
            raise RecruiterNotFoundError(f"Recruiter with ID '{id}' not found")
        del self._recruiters[id]
        self.save()

    def get_statistics(self) -> dict[str, int]:
        """Get recruiter statistics."""
        self._ensure_loaded()
        stats = {"total": 0, "pending": 0, "sent": 0, "replied": 0, "bounced": 0}

        for recruiter in self._recruiters.values():
            stats["total"] += 1
            stats[recruiter.status] += 1

        return stats

    def convert_format(self, target_format: Literal["csv", "json"]) -> Path:
        """Convert data to a different format."""
        self._ensure_loaded()

        if target_format == "csv":
            self._save_csv()
            return self.csv_path
        else:
            self._save_json()
            return self.json_path

    def create_sample_data(self, format: Literal["csv", "json"] | None = None) -> Path:
        """Create sample recruiter data file."""
        format = format or self.data_format
        self.config.data_path.mkdir(parents=True, exist_ok=True)

        sample_recruiters = [
            Recruiter(
                id="1",
                email="john.smith@techcorp.com",
                first_name="John",
                last_name="Smith",
                title="Mr.",
                company="TechCorp Inc.",
                job_title="Software Engineer",
                department="Engineering",
                greeting_style="semi_formal",
                custom_fields={"skills": "Python, React", "referral": "Jane Doe"},
                status="pending",
            ),
            Recruiter(
                id="2",
                email="sarah.jones@startup.io",
                first_name="Sarah",
                last_name="Jones",
                title="Ms.",
                company="Startup.io",
                job_title="Full Stack Developer",
                department="Product",
                greeting_style="casual",
                custom_fields={"notes": "Met at tech conference"},
                status="pending",
            ),
        ]

        self._recruiters = {r.id: r for r in sample_recruiters}

        if format == "json":
            self._save_json()
            return self.json_path
        else:
            self._save_csv()
            return self.csv_path
