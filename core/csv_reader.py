# core/csv_reader.py
# VoidSend - Subscriber list CSV parser

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


@dataclass
class Subscriber:
    email: str
    name: str = ""
    custom_fields: dict = field(default_factory=dict)

    def to_template_vars(self) -> dict:
        return {
            "email": self.email,
            "name": self.name,
            **self.custom_fields,
        }


@dataclass
class LoadResult:
    subscribers: list[Subscriber]
    skipped: list[tuple[int, str, str]]
    total_rows: int

    @property
    def valid_count(self) -> int:
        return len(self.subscribers)

    @property
    def skip_count(self) -> int:
        return len(self.skipped)


def load_subscribers(path: str | Path) -> LoadResult:
    """
    Load and validate a subscriber CSV.
    - Skips rows with missing or invalid email addresses.
    - Deduplicates by email (case-insensitive, keeps first occurrence).
    - Any column beyond 'email' and 'name' becomes a custom template field.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Subscriber list not found: {path}")

    subscribers: list[Subscriber] = []
    skipped: list[tuple[int, str, str]] = []
    seen_emails: set[str] = set()
    total_rows = 0

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames is None:
            raise ValueError("CSV file appears to be empty or has no headers.")

        fieldnames = [h.strip().lower() for h in reader.fieldnames]

        if "email" not in fieldnames:
            raise ValueError(
                "CSV must have an 'email' column. "
                f"Found columns: {', '.join(reader.fieldnames)}"
            )

        for row_num, row in enumerate(reader, start=2):
            total_rows += 1
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            raw_email = row.get("email", "").strip()

            if not raw_email:
                skipped.append((row_num, raw_email, "Empty email field"))
                continue

            if not EMAIL_REGEX.match(raw_email):
                skipped.append((row_num, raw_email, "Invalid email format"))
                continue

            email_lower = raw_email.lower()
            if email_lower in seen_emails:
                skipped.append((row_num, raw_email, "Duplicate email"))
                continue

            seen_emails.add(email_lower)
            name = row.get("name", "")
            custom_fields = {
                k: v for k, v in row.items()
                if k not in ("email", "name")
            }

            subscribers.append(Subscriber(
                email=raw_email,
                name=name,
                custom_fields=custom_fields,
            ))

    return LoadResult(
        subscribers=subscribers,
        skipped=skipped,
        total_rows=total_rows,
    )


def preview_csv(path: str | Path, max_rows: int = 5) -> list[Subscriber]:
    """Return first N valid subscribers for preview."""
    result = load_subscribers(path)
    return result.subscribers[:max_rows]
