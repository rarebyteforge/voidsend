# ui/app.py
# VoidSend - Main Textual TUI application

import time
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Header, Footer, DataTable, Button, Static
from textual.screen import Screen

from core.job_manager import JobManager, JobState, JobStatus
from core.notifier import NotificationConfig, notify_job_event
from ui.new_job_screen import NewJobScreen
from ui.setup_screen import SetupScreen
from config.settings import config_exists


class JobDashboard(Screen):

    BINDINGS = [
        Binding("n", "new_job",    "New Job"),
        Binding("l", "library",    "Library"),
        Binding("c", "cancel_job", "Cancel Job"),
        Binding("s", "settings",   "Settings"),
        Binding("q", "quit",       "Quit"),
    ]

    def __init__(self, job_manager: JobManager, smtp_config, **kwargs):
        super().__init__(**kwargs)
        self.job_manager = job_manager
        self.smtp_config = smtp_config

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static(" VoidSend — Newsletter Manager ", id="title_bar"),
            Horizontal(
                Static("", id="status_bar"),
                id="top_bar",
            ),
            DataTable(id="job_table"),
            Horizontal(
                Button("+ New Job [N]",  id="btn_new",      variant="success"),
                Button("Library [L]",    id="btn_library",  variant="default"),
                Button("Cancel Job [C]", id="btn_cancel",   variant="error"),
                Button("Settings [S]",   id="btn_settings", variant="default"),
                id="action_bar",
            ),
            id="main_container",
        )
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns(
            "Job ID",
            "Name",
            "Status",
            "Progress",
            "Sent",
            "Failed",
            "Elapsed",
            "Started",
        )
        self.set_interval(1.0, self.refresh_table)

    def refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()

        status_colors = {
            JobStatus.RUNNING:   "[green]▶ Running[/]",
            JobStatus.COMPLETED: "[blue]✓ Done[/]",
            JobStatus.CANCELLED: "[yellow]⏹ Cancelled[/]",
            JobStatus.FAILED:    "[red]✗ Failed[/]",
            JobStatus.PENDING:   "[dim]⏳ Pending[/]",
            JobStatus.PAUSED:    "[yellow]⏸ Paused[/]",
        }

        for state in self.job_manager.all_states():
            elapsed    = f"{int(state.elapsed_seconds)}s"
            progress   = f"{state.progress_pct:.0f}%"
            started    = time.strftime("%H:%M:%S", time.localtime(state.start_time))
            status_str = status_colors.get(state.status, state.status.value)

            table.add_row(
                state.job_id,
                state.name[:28],
                status_str,
                progress,
                str(state.sent),
                str(state.failed),
                elapsed,
                started,
            )

        active = self.job_manager.active_count()
        total  = len(self.job_manager.all_states())
        self.query_one("#status_bar", Static).update(
            f"  Jobs: {total} total | {active} active"
        )

    def action_new_job(self):
        self.app.push_screen(
            NewJobScreen(self.job_manager, self.smtp_config)
        )

    def action_library(self):
        from ui.library_screen import LibraryScreen
        self.app.push_screen(LibraryScreen())

    def action_cancel_job(self):
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            states = self.job_manager.all_states()
            if table.cursor_row < len(states):
                job_id = states[table.cursor_row].job_id
                self.job_manager.cancel_job(job_id)

    def action_settings(self):
        self.app.push_screen(SetupScreen())

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_new":
            self.action_new_job()
        elif event.button.id == "btn_library":
            self.action_library()
        elif event.button.id == "btn_cancel":
            self.action_cancel_job()
        elif event.button.id == "btn_settings":
            self.action_settings()


class VoidSendApp(App):

    CSS = """
    #main_container {
        height: 1fr;
        padding: 1 2;
    }
    #title_bar {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 0 1;
        text-style: bold;
    }
    #top_bar {
        height: 1;
        margin-bottom: 1;
    }
    #job_table {
        height: 1fr;
        border: solid $accent;
    }
    #action_bar {
        height: 3;
        margin-top: 1;
        align: center middle;
    }
    #action_bar Button {
        margin: 0 1;
        min-width: 18;
    }
    """

    def __init__(self, smtp_config=None, **kwargs):
        super().__init__(**kwargs)
        self.smtp_config      = smtp_config
        self.notification_cfg = NotificationConfig()
        self.job_manager      = JobManager(
            on_update=self._on_job_update
        )

    def _on_job_update(self, state: JobState):
        # Refresh dashboard
        try:
            screen = self.screen
            if isinstance(screen, JobDashboard):
                screen.refresh_table()
        except Exception:
            pass

        # Fire notifications on terminal states
        if state.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        ):
            import asyncio
            try:
                asyncio.ensure_future(
                    notify_job_event(
                        cfg         = self.notification_cfg,
                        smtp_config = self.smtp_config,
                        job_id      = state.job_id,
                        name        = state.name,
                        status      = state.status.value,
                        sent        = state.sent,
                        failed      = state.failed,
                        elapsed     = state.elapsed_seconds,
                    )
                )
            except Exception:
                pass

        # Milestone notifications (every 25%)
        if (
            self.notification_cfg.enabled
            and self.notification_cfg.milestones
            and state.status == JobStatus.RUNNING
        ):
            pct = state.progress_pct
            for milestone in (25, 50, 75):
                if abs(pct - milestone) < 1.0:
                    import asyncio
                    try:
                        asyncio.ensure_future(
                            notify_job_event(
                                cfg         = self.notification_cfg,
                                smtp_config = self.smtp_config,
                                job_id      = state.job_id,
                                name        = state.name,
                                status      = f"{milestone}% complete",
                                sent        = state.sent,
                                failed      = state.failed,
                                elapsed     = state.elapsed_seconds,
                            )
                        )
                    except Exception:
                        pass

    def on_mount(self):
        if not config_exists():
            self.push_screen(SetupScreen(first_run=True))
        else:
            self.push_screen(
                JobDashboard(self.job_manager, self.smtp_config)
            )
