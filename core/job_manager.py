# core/job_manager.py
# VoidSend - Multi-job queue and lifecycle manager

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

from core.mailer import SMTPConfig, SendResult, send_batch
from core.csv_reader import load_subscribers
from core.template import load_template_file, render_email
from logs.reporter import JobReporter


class JobStatus(Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    PAUSED    = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED    = "failed"


@dataclass
class JobConfig:
    name: str
    csv_path: str
    html_template_path: str
    subject_template: str
    smtp_config: SMTPConfig
    max_connections: int = 5
    delay_seconds: float = 0.3
    append_unsubscribe: bool = True
    plain_text_path: Optional[str] = None


@dataclass
class JobState:
    job_id: str
    name: str
    status: JobStatus
    total: int
    sent: int = 0
    failed: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    error_message: Optional[str] = None

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


class Job:
    def __init__(
        self,
        config: JobConfig,
        on_update: Optional[Callable[[JobState], None]] = None,
    ):
        self.job_id = str(uuid.uuid4())[:8].upper()
        self.config = config
        self.on_update = on_update
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.state = JobState(
            job_id=self.job_id,
            name=config.name,
            status=JobStatus.PENDING,
            total=0,
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
                self.state.status = JobStatus.FAILED
                self.state.error_message = "No valid subscribers found in CSV"
                self._notify()
                return

            html_template = load_template_file(self.config.html_template_path)
            plain_template = None
            if self.config.plain_text_path:
                plain_template = load_template_file(self.config.plain_text_path)

            recipients = []
            for sub in subscribers:
                rendered = render_email(
                    html_template=html_template,
                    subject_template=self.config.subject_template,
                    variables=sub.to_template_vars(),
                    append_unsubscribe=self.config.append_unsubscribe,
                    plain_text_template=plain_template,
                )
                recipients.append({
                    "email": sub.email,
                    "subject": rendered["subject"],
                    "html": rendered["html"],
                    "text": rendered["text"],
                })

            self.state.total = len(recipients)
            self.state.status = JobStatus.RUNNING
            self._notify()

            self.reporter = JobReporter(self.job_id, self.config.name)
            self.reporter.log_skipped(load_result.skipped)

            def on_result(result: SendResult):
                if result.success:
                    self.state.sent += 1
                else:
                    self.state.failed += 1
                self.reporter.log_result(result)
                self._notify()

            await send_batch(
                smtp_config=self.config.smtp_config,
                recipients=recipients,
                max_connections=self.config.max_connections,
                delay_seconds=self.config.delay_seconds,
                on_result=on_result,
                stop_event=self._stop_event,
            )

            self.state.end_time = time.time()
            self.state.status = (
                JobStatus.CANCELLED
                if self._stop_event.is_set()
                else JobStatus.COMPLETED
            )
            self.reporter.finalize(self.state)
            self._notify()

        except Exception as e:
            self.state.status = JobStatus.FAILED
            self.state.error_message = str(e)
            self.state.end_time = time.time()
            self._notify()

    def cancel(self):
        self._stop_event.set()

    def start(self):
        self._task = asyncio.ensure_future(self.run())
        return self._task


class JobManager:
    def __init__(self, on_update: Optional[Callable[[JobState], None]] = None):
        self._jobs: dict[str, Job] = {}
        self.on_update = on_update

    def create_job(self, config: JobConfig) -> Job:
        job = Job(config=config, on_update=self.on_update)
        self._jobs[job.job_id] = job
        return job

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
        return sum(1 for j in self._jobs.values() if j.state.is_active)
