# core/job_manager.py
# VoidSend - Multi-job queue and lifecycle manager
# Added: send_limit — cap how many emails are sent per job

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, Callable

from core.mailer import SMTPConfig, SendResult, send_batch
from core.csv_reader import load_subscribers
from core.template import load_template_file, render_email
from logs.reporter import JobReporter

HISTORY_FILE = Path.home() / ".voidsend" / "job_history.json"


class JobStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    PAUSED    = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED    = "failed"


@dataclass
class JobConfig:
    name:               str
    csv_path:           str
    html_template_path: str
    subject_template:   str
    smtp_config:        SMTPConfig
    max_connections:    int            = 5
    delay_seconds:      float          = 0.3
    append_unsubscribe: bool           = True
    plain_text_path:    Optional[str]  = None
    send_limit:         Optional[int]  = None  # None = send all

    def to_dict(self) -> dict:
        return {
            "name":               self.name,
            "csv_path":           self.csv_path,
            "html_template_path": self.html_template_path,
            "subject_template":   self.subject_template,
            "max_connections":    self.max_connections,
            "delay_seconds":      self.delay_seconds,
            "append_unsubscribe": self.append_unsubscribe,
            "plain_text_path":    self.plain_text_path,
            "send_limit":         self.send_limit,
        }


@dataclass
class JobState:
    job_id:        str
    name:          str
    status:        JobStatus
    total:         int
    sent:          int            = 0
    failed:        int            = 0
    start_time:    float          = field(default_factory=time.time)
    end_time:      Optional[float] = None
    error_message: Optional[str]  = None
    config_dict:   dict           = field(default_factory=dict)

    @property
    def elapsed_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def progress_pct(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.sent + self.failed) / self.total * 100

    @property
    def is_active(self) -> bool:
        return self.status in (JobStatus.RUNNING, JobStatus.PAUSED)

    def to_dict(self) -> dict:
        return {
            "job_id":        self.job_id,
            "name":          self.name,
            "status":        self.status.value,
            "total":         self.total,
            "sent":          self.sent,
            "failed":        self.failed,
            "start_time":    self.start_time,
            "end_time":      self.end_time,
            "error_message": self.error_message,
            "config_dict":   self.config_dict,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "JobState":
        return cls(
            job_id        = d.get("job_id", ""),
            name          = d.get("name", ""),
            status        = JobStatus(d.get("status", "completed")),
            total         = d.get("total", 0),
            sent          = d.get("sent", 0),
            failed        = d.get("failed", 0),
            start_time    = d.get("start_time", time.time()),
            end_time      = d.get("end_time"),
            error_message = d.get("error_message"),
            config_dict   = d.get("config_dict", {}),
        )


class Job:
    def __init__(
        self,
        config:    JobConfig,
        on_update: Optional[Callable[[JobState], None]] = None,
    ):
        self.job_id      = str(uuid.uuid4())[:8].upper()
        self.config      = config
        self.on_update   = on_update
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.state = JobState(
            job_id      = self.job_id,
            name        = config.name,
            status      = JobStatus.PENDING,
            total       = 0,
            config_dict = config.to_dict(),
        )
        self.reporter: Optional[JobReporter] = None

    def _notify(self):
        if self.on_update:
            self.on_update(self.state)

    async def run(self):
        try:
            load_result = load_subscribers(self.config.csv_path)
            subscribers = load_result.subscribers

            if not subscribers:
                self.state.status        = JobStatus.FAILED
                self.state.error_message = "No valid subscribers in CSV"
                self.state.end_time      = time.time()
                self._notify()
                return

            # ── Apply send limit ──────────────────────────────────────────
            if (
                self.config.send_limit
                and self.config.send_limit > 0
                and self.config.send_limit < len(subscribers)
            ):
                subscribers = subscribers[:self.config.send_limit]

            html_template  = load_template_file(
                self.config.html_template_path
            )
            plain_template = None
            if self.config.plain_text_path:
                plain_template = load_template_file(
                    self.config.plain_text_path
                )

            recipients = []
            for sub in subscribers:
                rendered = render_email(
                    html_template       = html_template,
                    subject_template    = self.config.subject_template,
                    variables           = sub.to_template_vars(),
                    append_unsubscribe  = self.config.append_unsubscribe,
                    plain_text_template = plain_template,
                )
                recipients.append({
                    "email":   sub.email,
                    "subject": rendered["subject"],
                    "html":    rendered["html"],
                    "text":    rendered["text"],
                })

            self.state.total  = len(recipients)
            self.state.status = JobStatus.RUNNING
            self._notify()

            self.reporter = JobReporter(self.job_id, self.config.name)
            self.reporter.log_skipped(load_result.skipped)

            def on_result(result: SendResult):
                if result.success:
                    self.state.sent   += 1
                else:
                    self.state.failed += 1
                self.reporter.log_result(result)
                self._notify()

            await send_batch(
                smtp_config     = self.config.smtp_config,
                recipients      = recipients,
                max_connections = self.config.max_connections,
                delay_seconds   = self.config.delay_seconds,
                on_result       = on_result,
                stop_event      = self._stop_event,
            )

            self.state.end_time = time.time()
            self.state.status   = (
                JobStatus.CANCELLED
                if self._stop_event.is_set()
                else JobStatus.COMPLETED
            )
            self.reporter.finalize(self.state)
            self._notify()

        except Exception as e:
            self.state.status        = JobStatus.FAILED
            self.state.error_message = str(e)
            self.state.end_time      = time.time()
            self._notify()

    def cancel(self):
        self._stop_event.set()

    def start(self):
        self._task = asyncio.ensure_future(self.run())
        return self._task


class JobManager:

    def __init__(
        self,
        on_update: Optional[Callable[[JobState], None]] = None,
    ):
        self._jobs:    dict[str, Job] = {}
        self._history: list[JobState] = []
        self.on_update = on_update
        self._load_history()

    def _load_history(self):
        if not HISTORY_FILE.exists():
            return
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._history = [JobState.from_dict(d) for d in data]
        except Exception:
            self._history = []

    def _save_history(self):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        terminal = [
            s for s in self.all_states()
            if s.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            )
        ]
        existing_ids = {s.job_id for s in self._history}
        for state in terminal:
            if state.job_id not in existing_ids:
                self._history.insert(0, state)
                existing_ids.add(state.job_id)
            else:
                for i, h in enumerate(self._history):
                    if h.job_id == state.job_id:
                        self._history[i] = state
                        break

        self._history = self._history[:100]
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    [s.to_dict() for s in self._history],
                    f, indent=2,
                )
        except Exception:
            pass

    def clear_history(self):
        self._history = []
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()

    def create_job(self, config: JobConfig) -> Job:
        job = Job(config=config, on_update=self._on_job_update)
        self._jobs[job.job_id] = job
        return job

    def _on_job_update(self, state: JobState):
        if self.on_update:
            self.on_update(state)
        if state.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ):
            self._save_history()

    def start_job(self, job: Job) -> asyncio.Task:
        return job.start()

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job and job.state.is_active:
            job.cancel()
            return True
        return False

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def all_states(self) -> list[JobState]:
        return [j.state for j in self._jobs.values()]

    def active_count(self) -> int:
        return sum(
            1 for j in self._jobs.values() if j.state.is_active
        )

    def get_history(self) -> list[JobState]:
        active_ids = {j.job_id for j in self._jobs.values()}
        return [
            s for s in self._history
            if s.job_id not in active_ids
        ]
