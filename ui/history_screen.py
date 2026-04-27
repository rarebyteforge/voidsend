# ui/history_screen.py
# VoidSend - Job history browser
# View past jobs, rerun them, or clear history

import time
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import (
    Button, Header, Footer,
    DataTable, Static
)
from typing import Optional
from core.job_manager import JobManager, JobState, JobStatus, JobConfig


class HistoryScreen(Screen):

    BINDINGS = [
        Binding("escape", "cancel",  "Back"),
        Binding("r",      "rerun",   "Rerun"),
        Binding("d",      "delete",  "Clear All"),
    ]

    CSS = """
    #history_container {
        height: 1fr;
        padding: 1 2;
    }
    #history_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 1;
    }
    #history_table {
        height: 1fr;
        border: solid $accent;
    }
    #selected_detail {
        height: 4;
        padding: 1;
        border: solid $panel;
        margin-top: 1;
        color: $text-muted;
    }
    #history_status {
        min-height: 1;
        margin-top: 1;
        padding: 0 1;
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
    """

    def __init__(
        self,
        job_manager: JobManager,
        smtp_config,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.job_manager = job_manager
        self.smtp_config = smtp_config
        self._history:  list[JobState] = []

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("🕐  Job History", id="history_title"),
            DataTable(id="history_table"),
            Static("", id="selected_detail"),
            Static("", id="history_status"),
            Horizontal(
                Button("▶ Rerun [R]",   id="btn_rerun",  variant="success"),
                Button("Clear All [D]", id="btn_clear",  variant="error"),
                Button("Back [ESC]",    id="btn_back",   variant="default"),
                id="action_bar",
            ),
            id="history_container",
        )
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns(
            "Job ID", "Name", "Status",
            "Sent", "Failed", "Date", "Duration",
        )
        self._load_table()

    def _load_table(self):
        table = self.query_one(DataTable)
        table.clear()
        self._history = self.job_manager.get_history()

        if not self._history:
            table.add_row(
                "[dim]No history yet[/dim]",
                "", "", "", "", "", "",
            )
            self._set_status("No past jobs found.", "dim")
            return

        status_colors = {
            JobStatus.COMPLETED: "[blue]✓ Done[/]",
            JobStatus.FAILED:    "[red]✗ Failed[/]",
            JobStatus.CANCELLED: "[yellow]⏹ Cancelled[/]",
        }

        for state in self._history:
            date = time.strftime(
                "%m/%d %H:%M",
                time.localtime(state.start_time)
            )
            elapsed = state.end_time - state.start_time if state.end_time else 0
            duration = f"{int(elapsed // 60)}m {int(elapsed % 60)}s"
            status_str = status_colors.get(
                state.status, state.status.value
            )
            table.add_row(
                state.job_id,
                state.name[:24],
                status_str,
                str(state.sent),
                str(state.failed),
                date,
                duration,
            )

        self._set_status(
            f"{len(self._history)} past jobs", "dim"
        )

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#history_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _selected_state(self) -> Optional[JobState]:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return None
        if table.cursor_row >= len(self._history):
            return None
        return self._history[table.cursor_row]

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ):
        """Show detail of selected job."""
        state = self._selected_state()
        if not state:
            return

        detail = self.query_one("#selected_detail", Static)
        cfg    = state.config_dict

        lines = []
        if state.error_message:
            lines.append(
                f"[red]Error: {state.error_message[:70]}[/red]"
            )
        if cfg.get("csv_path"):
            lines.append(
                f"CSV: {cfg['csv_path'].split('/')[-1]}"
            )
        if cfg.get("subject_template"):
            lines.append(
                f"Subject: {cfg['subject_template'][:50]}"
            )
        if cfg.get("html_template_path"):
            lines.append(
                f"Template: {cfg['html_template_path'].split('/')[-1]}"
            )

        detail.update("\n".join(lines) if lines else "[dim]No details[/dim]")

    def _rerun_selected(self):
        state = self._selected_state()
        if not state:
            self._set_status("✗ Select a job to rerun", "red")
            return

        cfg_dict = state.config_dict
        if not cfg_dict:
            self._set_status("✗ No config saved for this job", "red")
            return

        if not self.smtp_config:
            self._set_status(
                "✗ No SMTP config loaded. Go to Settings first.", "red"
            )
            return

        # Check files still exist
        csv_path  = cfg_dict.get("csv_path", "")
        html_path = cfg_dict.get("html_template_path", "")

        from pathlib import Path
        missing = []
        if not csv_path or not Path(csv_path).exists():
            missing.append(f"CSV not found: {csv_path.split('/')[-1]}")
        if not html_path or not Path(html_path).exists():
            missing.append(
                f"Template not found: {html_path.split('/')[-1]}"
            )

        if missing:
            self._set_status(
                "✗ " + " | ".join(missing), "red"
            )
            return

        cfg = JobConfig(
            name               = cfg_dict.get("name", state.name),
            csv_path           = csv_path,
            html_template_path = html_path,
            subject_template   = cfg_dict.get("subject_template", ""),
            smtp_config        = self.smtp_config,
            max_connections    = cfg_dict.get("max_connections", 5),
            delay_seconds      = cfg_dict.get("delay_seconds", 0.3),
            append_unsubscribe = cfg_dict.get("append_unsubscribe", True),
            plain_text_path    = cfg_dict.get("plain_text_path"),
        )

        job = self.job_manager.create_job(cfg)
        self.job_manager.start_job(job)
        self._set_status(
            f"✓ Rerunning as job {job.job_id} — check dashboard",
            "green",
        )

    def _clear_history(self):
        self.job_manager.clear_history()
        self._load_table()
        self._set_status("✓ History cleared", "yellow")
        self.query_one(
            "#selected_detail", Static
        ).update("")

    def action_rerun(self):
        self._rerun_selected()

    def action_delete(self):
        self._clear_history()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_rerun":
            self._rerun_selected()
        elif event.button.id == "btn_clear":
            self._clear_history()
        elif event.button.id == "btn_back":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()
