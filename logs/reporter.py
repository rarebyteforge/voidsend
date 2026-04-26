# logs/reporter.py
# VoidSend - Per-job delivery logging (JSON + CSV)

import csv
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.job_manager import JobState

from core.mailer import SendResult

LOGS_DIR = Path.home() / ".voidsend" / "logs"


class JobReporter:
    def __init__(self, job_id: str, job_name: str):
        self.job_id = job_id
        self.job_name = job_name
        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c if c.isalnum() else "_" for c in job_name)
        base = LOGS_DIR / f"{timestamp}_{job_id}_{safe_name}"

        self._json_path = base.with_suffix(".json")
        self._csv_path  = base.with_suffix(".csv")
        self._results: list[dict] = []
        self._skipped: list[dict] = []

        with open(self._csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp", "email", "status", "error", "duration_ms"]
            )
            writer.writeheader()

    def log_result(self, result: SendResult):
        row = {
            "timestamp":   time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(result.timestamp)),
            "email":       result.email,
            "status":      "success" if result.success else "failed",
            "error":       result.error or "",
            "duration_ms": round(result.duration_ms, 1),
        }
        self._results.append(row)

        with open(self._csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["timestamp", "email", "status", "error", "duration_ms"]
            )
            writer.writerow(row)

    def log_skipped(self, skipped: list[tuple[int, str, str]]):
        self._skipped = [
            {"row": row_num, "email": email, "reason": reason}
            for row_num, email, reason in skipped
        ]

    def finalize(self, state: "JobState"):
        summary = {
            "job_id":           self.job_id,
            "job_name":         self.job_name,
            "status":           state.status.value,
            "total_recipients": state.total,
            "sent_success":     state.sent,
            "sent_failed":      state.failed,
            "elapsed_seconds":  round(state.elapsed_seconds, 1),
            "start_time":       time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state.start_time)),
            "end_time":         time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state.end_time or time.time())),
            "skipped_on_load":  self._skipped,
            "results":          self._results,
        }
        with open(self._json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    @property
    def csv_path(self) -> Path:
        return self._csv_path

    @property
    def json_path(self) -> Path:
        return self._json_path


def list_logs() -> list[Path]:
    """Return all log files sorted newest first."""
    if not LOGS_DIR.exists():
        return []
    return sorted(LOGS_DIR.glob("*.json"), reverse=True)
