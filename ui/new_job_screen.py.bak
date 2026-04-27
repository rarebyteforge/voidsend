# ui/new_job_screen.py
# VoidSend - New job creation form
# Keyboard fix: all text inputs use InputDialog for Termux reliability

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Header, Footer, Input,
    Label, Static, Select
)
from typing import Optional

from core.csv_reader import load_subscribers
from core.job_manager import JobConfig, JobManager
from core.mailer import SMTPConfig
from core.content_generator import ContentFields, GeneratedContent


SOURCE_OPTIONS = [
    ("Use Files (HTML template + CSV)", "files"),
    ("Build Content (generator)",       "build"),
    ("From Library (saved templates)",  "library"),
]


class NewJobScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    #new_job_container {
        height: 1fr;
        padding: 1 2;
    }
    #form_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 1;
    }
    #form_scroll {
        height: 1fr;
        border: solid $accent;
        padding: 1 2;
    }
    #action_bar {
        height: auto;
        margin-top: 1;
        padding: 1 0;
    }
    #action_bar Button {
        margin: 0 1;
        min-width: 16;
        height: 3;
    }
    #options_row {
        height: auto;
        margin-top: 1;
    }
    #content_btns Button {
        margin: 0 1;
        min-width: 18;
        height: 3;
    }
    .field_row {
        height: auto;
        margin-bottom: 1;
    }
    .field_row Static {
        width: 1fr;
        height: 3;
        border: solid $panel;
        padding: 0 1;
        content-align: left middle;
        background: $panel;
    }
    .field_row Button {
        width: 10;
        min-width: 10;
        margin-left: 1;
        height: 3;
    }
    .path_row {
        height: auto;
        margin-bottom: 1;
    }
    .path_row Input {
        width: 1fr;
    }
    .path_row Button {
        width: 10;
        min-width: 10;
        margin-left: 1;
    }
    Label {
        margin-top: 1;
    }
    Input {
        margin-bottom: 1;
    }
    Select {
        margin-bottom: 1;
    }
    #status_msg {
        margin-top: 1;
        min-height: 1;
    }
    #preview_info {
        margin-top: 1;
        min-height: 2;
    }
    #generated_status {
        min-height: 1;
        margin-bottom: 1;
    }
    """

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
        self._source      = "files"

        # Store values since we use dialog instead of live Input
        self._job_name  = ""
        self._csv_path  = ""
        self._html_path = ""
        self._text_path = ""
        self._subject   = ""
        self._max_conn  = "5"
        self._delay     = "0.3"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static("✉  Create New Send Job", id="form_title"),
            ScrollableContainer(

                # ── Job Name ──────────────────────────────────────────────
                Label("Job Name"),
                Horizontal(
                    Static(
                        "[dim]Tap edit to enter job name[/dim]",
                        id="val_job_name",
                    ),
                    Button("edit", id="btn_edit_job_name", variant="default"),
                    classes="field_row",
                ),

                # ── Subscriber CSV ────────────────────────────────────────
                Label("Subscriber CSV"),
                Horizontal(
                    Static(
                        "[dim]Tap browse to select CSV[/dim]",
                        id="val_csv_path",
                    ),
                    Button("browse", id="btn_browse_csv", variant="default"),
                    classes="field_row",
                ),
                Static("", id="preview_info"),

                # ── Content Source ────────────────────────────────────────
                Label("Content Source"),
                Select(
                    options=SOURCE_OPTIONS,
                    id="source_select",
                    value="files",
                ),

                # ── Files mode ────────────────────────────────────────────
                Label("HTML Template", id="lbl_html"),
                Horizontal(
                    Static(
                        "[dim]Tap browse to select HTML template[/dim]",
                        id="val_html_path",
                    ),
                    Button("browse", id="btn_browse_html", variant="default"),
                    classes="field_row",
                    id="html_row",
                ),
                Label("Plain Text Template (optional)", id="lbl_text"),
                Horizontal(
                    Static(
                        "[dim]Tap browse (optional)[/dim]",
                        id="val_text_path",
                    ),
                    Button("browse", id="btn_browse_text", variant="default"),
                    classes="field_row",
                    id="text_row",
                ),
                Label(
                    "Subject Line (supports {{name}}, {{email}})",
                    id="lbl_subject",
                ),
                Horizontal(
                    Static(
                        "[dim]Tap edit to enter subject[/dim]",
                        id="val_subject",
                    ),
                    Button("edit", id="btn_edit_subject", variant="default"),
                    classes="field_row",
                    id="subject_row",
                ),

                # ── Builder/Library mode ──────────────────────────────────
                Static("", id="generated_status"),
                Horizontal(
                    Button(
                        "Content Builder",
                        id="btn_open_builder",
                        variant="default",
                    ),
                    Button(
                        "Library",
                        id="btn_open_library",
                        variant="default",
                    ),
                    id="content_btns",
                ),

                # ── Options ───────────────────────────────────────────────
                Label("Options"),
                Horizontal(
                    Vertical(
                        Label("Unsub Footer"),
                        Select(
                            options=[
                                ("Yes", "yes"),
                                ("No",  "no"),
                            ],
                            id="unsubscribe",
                            value="yes",
                        ),
                    ),
                    Vertical(
                        Label("Max Conn"),
                        Horizontal(
                            Static("5", id="val_max_conn"),
                            Button("edit", id="btn_edit_max_conn",
                                   variant="default"),
                            classes="field_row",
                        ),
                    ),
                    Vertical(
                        Label("Delay (sec)"),
                        Horizontal(
                            Static("0.3", id="val_delay"),
                            Button("edit", id="btn_edit_delay",
                                   variant="default"),
                            classes="field_row",
                        ),
                    ),
                    id="options_row",
                ),

                Static("", id="status_msg"),
                id="form_scroll",
            ),

            # ── Action bar always visible ─────────────────────────────────
            Horizontal(
                Button("Preview CSV", id="btn_preview", variant="default"),
                Button("Launch",      id="btn_launch",  variant="success"),
                Button("Cancel",      id="btn_cancel",  variant="error"),
                id="action_bar",
            ),
            id="new_job_container",
        )
        yield Footer()

    def on_mount(self):
        self.call_after_refresh(self._init_view)

    def _init_view(self):
        self._apply_source("files")
        try:
            self.query_one(
                "#form_scroll", ScrollableContainer
            ).scroll_home(animate=False)
        except Exception:
            pass

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "source_select":
            self._source = str(event.value)
            self._apply_source(self._source)

    def _apply_source(self, source: str):
        is_files = source == "files"
        for wid in ["lbl_html", "html_row", "lbl_text",
                    "text_row", "lbl_subject", "subject_row"]:
            try:
                self.query_one(f"#{wid}").display = is_files
            except Exception:
                pass
        for wid in ["generated_status", "content_btns"]:
            try:
                self.query_one(f"#{wid}").display = not is_files
            except Exception:
                pass

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#status_msg", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _set_preview(self, msg: str):
        self.query_one("#preview_info", Static).update(msg)

    def _set_field(self, widget_id: str, value: str, dim_if_empty: bool = True):
        """Update a display Static with the current value."""
        try:
            w = self.query_one(f"#{widget_id}", Static)
            if value:
                w.update(value)
            elif dim_if_empty:
                w.update("[dim]not set[/dim]")
        except Exception:
            pass

    # ── Input dialogs ─────────────────────────────────────────────────────────

    def _edit_job_name(self):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            self._job_name = val
            self._set_field("val_job_name", val)
        self.app.push_screen(InputDialog(
            title         = "Job Name",
            label         = "Enter a name for this send job:",
            on_submit     = on_submit,
            initial_value = self._job_name,
            hint          = "e.g. August Newsletter 2026",
        ))

    def _edit_subject(self):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            self._subject = val
            self._set_field("val_subject", val)
        self.app.push_screen(InputDialog(
            title         = "Subject Line",
            label         = "Enter email subject line:",
            on_submit     = on_submit,
            initial_value = self._subject,
            hint          = "Supports {{name}}, {{email}} placeholders",
        ))

    def _edit_max_conn(self):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            self._max_conn = val
            self._set_field("val_max_conn", val)
        def validate(val: str):
            try:
                n = int(val)
                if not 1 <= n <= 20:
                    return "Must be between 1 and 20"
            except ValueError:
                return "Must be a number"
        self.app.push_screen(InputDialog(
            title         = "Max Connections",
            label         = "Concurrent SMTP connections (1-20):",
            on_submit     = on_submit,
            initial_value = self._max_conn,
            hint          = "Recommended: 3-5 for free SMTP providers",
            validator     = validate,
        ))

    def _edit_delay(self):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            self._delay = val
            self._set_field("val_delay", val)
        def validate(val: str):
            try:
                f = float(val)
                if f < 0:
                    return "Cannot be negative"
            except ValueError:
                return "Must be a number e.g. 0.3"
        self.app.push_screen(InputDialog(
            title         = "Delay Between Sends",
            label         = "Seconds to wait between each email:",
            on_submit     = on_submit,
            initial_value = self._delay,
            hint          = "0.3 recommended for Brevo free tier",
            validator     = validate,
        ))

    # ── File browsers ─────────────────────────────────────────────────────────

    def _browse_csv(self):
        from ui.file_browser import FileBrowserScreen
        def on_picked(path: str):
            self._csv_path = path
            # Truncate display path for readability
            display = path.split("/")[-1]
            self._set_field("val_csv_path", display)
            self._preview_csv_path(path)
        self.app.push_screen(FileBrowserScreen(
            on_select  = on_picked,
            filter_ext = [".csv"],
            title      = "Select Subscriber CSV",
        ))

    def _browse_html(self):
        from ui.file_browser import FileBrowserScreen
        def on_picked(path: str):
            self._html_path = path
            display = path.split("/")[-1]
            self._set_field("val_html_path", display)
        self.app.push_screen(FileBrowserScreen(
            on_select  = on_picked,
            filter_ext = [".html", ".htm"],
            title      = "Select HTML Template",
        ))

    def _browse_text(self):
        from ui.file_browser import FileBrowserScreen
        def on_picked(path: str):
            self._text_path = path
            display = path.split("/")[-1]
            self._set_field("val_text_path", display)
        self.app.push_screen(FileBrowserScreen(
            on_select  = on_picked,
            filter_ext = [".txt"],
            title      = "Select Plain Text Template",
        ))

    # ── CSV preview ───────────────────────────────────────────────────────────

    def _preview_csv_path(self, path: str):
        try:
            result = load_subscribers(path)
            lines  = [
                f"[green]✓ {result.valid_count} valid[/green]"
                f"  [yellow]{result.skip_count} skipped[/yellow]",
            ]
            for sub in result.subscribers[:3]:
                lines.append(f"  • {sub.email}  {sub.name}")
            if result.valid_count > 3:
                lines.append(
                    f"  [dim]... and {result.valid_count - 3} more[/dim]"
                )
            self._set_preview("\n".join(lines))
        except Exception as e:
            self._set_status(f"✗ CSV error: {e}", "red")

    def _preview_csv(self):
        if not self._csv_path:
            self._set_status("✗ Browse to a CSV first", "red")
            return
        self._preview_csv_path(self._csv_path)

    # ── Builder / Library ─────────────────────────────────────────────────────

    def _open_builder(self):
        from ui.content_screen import ContentScreen
        def on_content_ready(
            fields: ContentFields,
            generated: GeneratedContent,
        ):
            self._generated = generated
            try:
                self.query_one("#generated_status", Static).update(
                    f"[green]✓ Content ready: \"{fields.headline}\"[/green]"
                )
            except Exception:
                pass
        self.app.push_screen(ContentScreen(on_complete=on_content_ready))

    def _open_library(self):
        from ui.library_screen import LibraryScreen
        def on_template_selected(
            fields: ContentFields,
            generated: GeneratedContent,
        ):
            self._generated = generated
            try:
                self.query_one("#generated_status", Static).update(
                    f"[green]✓ Template: \"{fields.template_name or fields.headline}\"[/green]"
                )
            except Exception:
                pass
        self.app.push_screen(LibraryScreen(on_select=on_template_selected))

    # ── Launch ────────────────────────────────────────────────────────────────

    def _validate_and_launch(self):
        errors = []

        if not self._job_name:
            errors.append("Job name required — tap edit")
        if not self._csv_path or not Path(self._csv_path).exists():
            errors.append("Valid CSV required — tap browse")

        html_path = text_path = subject = None

        if self._source == "files":
            if not self._html_path or not Path(self._html_path).exists():
                errors.append("HTML template required — tap browse")
            if not self._subject:
                errors.append("Subject required — tap edit")
            html_path = self._html_path
            text_path = self._text_path or None
            subject   = self._subject
        else:
            if not self._generated:
                errors.append(
                    "No content loaded — use Builder or Library"
                )

        try:
            max_conn = int(self._max_conn)
            if not 1 <= max_conn <= 20:
                errors.append("Connections must be 1-20")
        except ValueError:
            max_conn = 5

        try:
            delay = float(self._delay)
        except ValueError:
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

        unsubscribe = str(
            self.query_one("#unsubscribe", Select).value
        ) == "yes"

        cfg = JobConfig(
            name               = self._job_name,
            csv_path           = self._csv_path,
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
        bid = event.button.id
        if bid == "btn_edit_job_name":
            self._edit_job_name()
        elif bid == "btn_browse_csv":
            self._browse_csv()
        elif bid == "btn_browse_html":
            self._browse_html()
        elif bid == "btn_browse_text":
            self._browse_text()
        elif bid == "btn_edit_subject":
            self._edit_subject()
        elif bid == "btn_edit_max_conn":
            self._edit_max_conn()
        elif bid == "btn_edit_delay":
            self._edit_delay()
        elif bid == "btn_preview":
            self._preview_csv()
        elif bid == "btn_open_builder":
            self._open_builder()
        elif bid == "btn_open_library":
            self._open_library()
        elif bid == "btn_launch":
            self._validate_and_launch()
        elif bid == "btn_cancel":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()
