# ui/new_job_screen.py
# VoidSend - New job creation form
# Three content sources: Use Files | Build Content | From Library

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, Header, Footer, Input,
    Label, Static, Switch, Select
)
from typing import Optional

from core.csv_reader import load_subscribers
from core.job_manager import JobConfig, JobManager
from core.mailer import SMTPConfig
from core.content_generator import ContentFields, GeneratedContent


SOURCE_OPTIONS = [
    ("📁  Use Files (HTML template + CSV)", "files"),
    ("✏   Build Content (generator)",       "build"),
    ("📚  From Library (saved templates)",  "library"),
]


class NewJobScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(
        self,
        job_manager: JobManager,
        smtp_config: SMTPConfig,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.job_manager  = job_manager
        self.smtp_config  = smtp_config
        self._generated: Optional[GeneratedContent] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("✉  Create New Send Job", id="form_title"),
            Vertical(
                Label("Job Name"),
                Input(placeholder="e.g. August Newsletter", id="job_name"),
                Label("Subscriber CSV Path"),
                Input(placeholder="/path/to/subscribers.csv", id="csv_path"),
                Label("Content Source"),
                Select(
                    options=SOURCE_OPTIONS,
                    id="source_select",
                    value="files",
                ),
                Vertical(
                    Label("HTML Template Path"),
                    Input(
                        placeholder="/path/to/template.html",
                        id="html_path",
                    ),
                    Label("Plain Text Template Path (optional)"),
                    Input(
                        placeholder="/path/to/template.txt",
                        id="text_path",
                    ),
                    id="files_section",
                ),
                Vertical(
                    Static("", id="generated_status"),
                    Horizontal(
                        Button(
                            "✏  Open Content Builder",
                            id="btn_open_builder",
                            variant="default",
                        ),
                        Button(
                            "📚  Open Library",
                            id="btn_open_library",
                            variant="default",
                        ),
                        id="content_btns",
                    ),
                    id="content_section",
                ),
                Label("Subject Line (supports {{name}}, {{email}})"),
                Input(
                    placeholder="Hello {{name}}, here's your update!",
                    id="subject",
                ),
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
                    Button("Preview CSV",  id="btn_preview", variant="default"),
                    Button("▶ Launch Job", id="btn_launch",  variant="success"),
                    Button("Cancel [ESC]", id="btn_cancel",  variant="error"),
                    id="btn_row",
                ),
                id="form_inner",
            ),
            id="new_job_container",
        )
        yield Footer()

    def on_mount(self):
        self._update_source_visibility("files")

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "source_select":
            self._update_source_visibility(str(event.value))

    def _update_source_visibility(self, source: str):
        self.query_one("#files_section").display   = (source == "files")
        self.query_one("#content_section").display = (source != "files")
        self.query_one("#subject").display         = (source == "files")

    def _current_source(self) -> str:
        return str(self.query_one("#source_select", Select).value)

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#status_msg", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _set_preview(self, msg: str):
        self.query_one("#preview_info", Static).update(msg)

    def _set_generated_status(self, msg: str, color: str = "green"):
        self.query_one("#generated_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _preview_csv(self):
        csv_path = self.query_one("#csv_path", Input).value.strip()
        if not csv_path:
            self._set_status("✗ Enter a CSV path first", "red")
            return
        try:
            result = load_subscribers(csv_path)
            lines = [
                f"[green]✓ {result.valid_count} valid[/green]"
                f"  [yellow]{result.skip_count} skipped[/yellow]",
            ]
            for sub in result.subscribers[:3]:
                lines.append(f"  • {sub.email}  {sub.name}")
            if result.valid_count > 3:
                lines.append(f"  ... and {result.valid_count - 3} more")
            self._set_preview("\n".join(lines))
        except Exception as e:
            self._set_status(f"✗ CSV error: {e}", "red")

    def _open_builder(self):
        from ui.content_screen import ContentScreen

        def on_content_ready(
            fields: ContentFields,
            generated: GeneratedContent,
        ):
            self._generated = generated
            self._set_generated_status(
                f"✓ Content ready: \"{fields.headline}\" "
                f"({fields.layout})",
                "green",
            )

        self.app.push_screen(ContentScreen(on_complete=on_content_ready))

    def _open_library(self):
        from ui.library_screen import LibraryScreen

        def on_template_selected(
            fields: ContentFields,
            generated: GeneratedContent,
        ):
            self._generated = generated
            self._set_generated_status(
                f"✓ Template loaded: "
                f"\"{fields.template_name or fields.headline}\"",
                "green",
            )

        self.app.push_screen(LibraryScreen(on_select=on_template_selected))

    def _validate_and_launch(self):
        job_name = self.query_one("#job_name", Input).value.strip()
        csv_path = self.query_one("#csv_path", Input).value.strip()
        source   = self._current_source()
        errors   = []

        if not job_name:
            errors.append("Job name required")
        if not csv_path or not Path(csv_path).exists():
            errors.append("Valid CSV path required")

        html_path = text_path = subject = None

        if source == "files":
            html_path = self.query_one("#html_path", Input).value.strip()
            text_path = self.query_one("#text_path", Input).value.strip() or None
            subject   = self.query_one("#subject", Input).value.strip()
            if not html_path or not Path(html_path).exists():
                errors.append("Valid HTML template path required")
            if not subject:
                errors.append("Subject line required")
        else:
            if not self._generated:
                errors.append(
                    "No content loaded — use Builder or Library first"
                )

        try:
            max_conn = int(self.query_one("#max_conn", Input).value.strip())
            if not 1 <= max_conn <= 20:
                errors.append("Connections must be 1-20")
        except ValueError:
            errors.append("Max connections must be a number")
            max_conn = 5

        try:
            delay = float(self.query_one("#delay", Input).value.strip())
            if delay < 0:
                errors.append("Delay cannot be negative")
        except ValueError:
            errors.append("Delay must be a number")
            delay = 0.3

        if errors:
            self._set_status("✗ " + " | ".join(errors), "red")
            return

        if not self.smtp_config:
            self._set_status(
                "✗ No SMTP config. Go to Settings first.", "red"
            )
            return

        if self._generated:
            from pathlib import Path as P
            tmp = P.home() / ".voidsend" / "generated_content.html"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(self._generated.html, encoding="utf-8")
            html_path = str(tmp)
            subject   = self._generated.subject

        unsubscribe = self.query_one("#unsubscribe", Switch).value

        cfg = JobConfig(
            name               = job_name,
            csv_path           = csv_path,
            html_template_path = html_path,
            subject_template   = subject,
            smtp_config        = self.smtp_config,
            max_connections    = max_conn,
            delay_seconds      = delay,
            append_unsubscribe = unsubscribe,
            plain_text_path    = text_path,
        )

        job = self.job_manager.create_job(cfg)
        self.job_manager.start_job(job)
        self._set_status(f"✓ Job {job.job_id} launched!", "green")
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_preview":
            self._preview_csv()
        elif event.button.id == "btn_open_builder":
            self._open_builder()
        elif event.button.id == "btn_open_library":
            self._open_library()
        elif event.button.id == "btn_launch":
            self._validate_and_launch()
        elif event.button.id == "btn_cancel":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()
