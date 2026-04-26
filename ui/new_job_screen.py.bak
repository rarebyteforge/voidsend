# ui/new_job_screen.py
# VoidSend - New job creation form

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Header, Footer, Input, Label, Static, Switch

from core.csv_reader import load_subscribers
from core.job_manager import JobConfig, JobManager
from core.mailer import SMTPConfig


class NewJobScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, job_manager: JobManager, smtp_config: SMTPConfig, **kwargs):
        super().__init__(**kwargs)
        self.job_manager = job_manager
        self.smtp_config = smtp_config

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("✉  Create New Send Job", id="form_title"),
            Vertical(
                Label("Job Name"),
                Input(placeholder="e.g. August Newsletter", id="job_name"),
                Label("Subscriber CSV Path"),
                Input(placeholder="/path/to/subscribers.csv", id="csv_path"),
                Label("HTML Template Path"),
                Input(placeholder="/path/to/template.html", id="html_path"),
                Label("Subject Line (supports {{name}}, {{email}})"),
                Input(
                    placeholder="Hello {{name}}, here's your update!",
                    id="subject",
                ),
                Label("Plain Text Template Path (optional)"),
                Input(placeholder="/path/to/template.txt", id="text_path"),
                Horizontal(
                    Vertical(
                        Label("Unsubscribe Footer"),
                        Switch(id="unsubscribe", value=True),
                    ),
                    Vertical(
                        Label("Max Connections"),
                        Input(value="5", id="max_conn"),
                    ),
                    Vertical(
                        Label("Delay (seconds)"),
                        Input(value="0.3", id="delay"),
                    ),
                    id="options_row",
                ),
                Static("", id="preview_info"),
                Static("", id="status_msg"),
                Horizontal(
                    Button("Preview CSV", id="btn_preview", variant="default"),
                    Button("▶ Launch Job", id="btn_launch", variant="success"),
                    Button("Cancel", id="btn_cancel", variant="error"),
                    id="btn_row",
                ),
                id="form_inner",
            ),
            id="new_job_container",
        )
        yield Footer()

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#status_msg", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _set_preview(self, msg: str):
        self.query_one("#preview_info", Static).update(msg)

    def _preview_csv(self):
        csv_path = self.query_one("#csv_path", Input).value.strip()
        if not csv_path:
            self._set_status("✗ Enter a CSV path first", "red")
            return
        try:
            result = load_subscribers(csv_path)
            lines = [
                f"[green]✓ {result.valid_count} valid subscribers[/green]"
                f"  [yellow]{result.skip_count} skipped[/yellow]",
            ]
            for sub in result.subscribers[:3]:
                lines.append(f"  • {sub.email}  {sub.name}")
            if result.valid_count > 3:
                lines.append(f"  ... and {result.valid_count - 3} more")
            self._set_preview("\n".join(lines))
        except Exception as e:
            self._set_status(f"✗ CSV error: {e}", "red")

    def _validate_and_launch(self):
        job_name  = self.query_one("#job_name", Input).value.strip()
        csv_path  = self.query_one("#csv_path", Input).value.strip()
        html_path = self.query_one("#html_path", Input).value.strip()
        subject   = self.query_one("#subject", Input).value.strip()
        text_path = self.query_one("#text_path", Input).value.strip() or None
        unsubscribe = self.query_one("#unsubscribe", Switch).value
        max_conn_str = self.query_one("#max_conn", Input).value.strip()
        delay_str    = self.query_one("#delay", Input).value.strip()

        errors = []
        if not job_name:
            errors.append("Job name required")
        if not csv_path or not Path(csv_path).exists():
            errors.append("Valid CSV path required")
        if not html_path or not Path(html_path).exists():
            errors.append("Valid HTML template path required")
        if not subject:
            errors.append("Subject line required")

        try:
            max_conn = int(max_conn_str)
            if not 1 <= max_conn <= 20:
                errors.append("Connections must be 1-20")
        except ValueError:
            errors.append("Max connections must be a number")
            max_conn = 5

        try:
            delay = float(delay_str)
            if delay < 0:
                errors.append("Delay cannot be negative")
        except ValueError:
            errors.append("Delay must be a number")
            delay = 0.3

        if errors:
            self._set_status("✗ " + " | ".join(errors), "red")
            return

        if not self.smtp_config:
            self._set_status("✗ No SMTP config loaded. Go to Settings first.", "red")
            return

        cfg = JobConfig(
            name=job_name,
            csv_path=csv_path,
            html_template_path=html_path,
            subject_template=subject,
            smtp_config=self.smtp_config,
            max_connections=max_conn,
            delay_seconds=delay,
            append_unsubscribe=unsubscribe,
            plain_text_path=text_path,
        )

        job = self.job_manager.create_job(cfg)
        self.job_manager.start_job(job)
        self._set_status(f"✓ Job {job.job_id} launched!", "green")
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_preview":
            self._preview_csv()
        elif event.button.id == "btn_launch":
            self._validate_and_launch()
        elif event.button.id == "btn_cancel":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()
