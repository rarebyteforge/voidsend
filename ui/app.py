# ui/app.py
# VoidSend - Main TUI app
# Fixed: Header compatibility, retry bar, hacker green theme

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

RETRYABLE = (JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.COMPLETED)


class JobDashboard(Screen):

    BINDINGS = [
        Binding("n", "new_job",    "New Job"),
        Binding("l", "library",    "Library"),
        Binding("h", "history",    "History"),
        Binding("f", "raffle",     "Raffle"),
        Binding("r", "retry_job",  "Retry"),
        Binding("c", "cancel_job", "Cancel"),
        Binding("s", "settings",   "Settings"),
        Binding("q", "quit",       "Quit"),
    ]

    def __init__(self, job_manager: JobManager, smtp_config, **kwargs):
        super().__init__(**kwargs)
        self.job_manager = job_manager
        self.smtp_config = smtp_config

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(
                "▓▒░ VOIDSEND — NEWSLETTER MANAGER ░▒▓",
                id="title_bar",
            ),
            Static("", id="status_bar"),
            DataTable(id="job_table"),
            Static("", id="job_error_msg"),
            Horizontal(
                Button("+ NEW",    id="btn_new",     variant="success"),
                Button("LIBRARY",  id="btn_library", variant="default"),
                Button("HISTORY",  id="btn_history", variant="default"),
                Button("RAFFLE",   id="btn_raffle",  variant="default"),
                id="btn_row1",
            ),
            Horizontal(
                Button("CANCEL",   id="btn_cancel",   variant="default"),
                Button("SETTINGS", id="btn_settings", variant="default"),
                Button("QUIT",     id="btn_quit",     variant="default"),
                id="btn_row2",
            ),
            Static("", id="retry_bar"),
            id="main_container",
        )
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns(
            "ID", "NAME", "STATUS",
            "PROG", "SENT", "FAIL",
            "TIME", "START",
        )
        self.set_interval(1.0, self.refresh_table)
        self._update_retry_bar()

    def refresh_table(self):
        table = self.query_one(DataTable)
        table.clear()

        status_colors = {
            JobStatus.RUNNING:   "[bold green]▶ RUN[/]",
            JobStatus.COMPLETED: "[bold cyan]✓ DONE[/]",
            JobStatus.CANCELLED: "[yellow]⏹ STOP[/]",
            JobStatus.FAILED:    "[bold red]✗ FAIL[/]",
            JobStatus.PENDING:   "[dim]⏳ WAIT[/]",
            JobStatus.PAUSED:    "[yellow]⏸ PAUSE[/]",
        }

        for state in self.job_manager.all_states():
            elapsed    = f"{int(state.elapsed_seconds)}s"
            progress   = f"{state.progress_pct:.0f}%"
            started    = time.strftime(
                "%H:%M", time.localtime(state.start_time)
            )
            status_str = status_colors.get(
                state.status, state.status.value
            )
            table.add_row(
                state.job_id,
                state.name[:16],
                status_str,
                progress,
                str(state.sent),
                str(state.failed),
                elapsed,
                started,
            )

        active = self.job_manager.active_count()
        total  = len(self.job_manager.all_states())
        hist   = len(self.job_manager.get_history())

        self.query_one("#status_bar", Static).update(
            f"  [green]●[/green] ACTIVE: [bold green]{active}[/bold green]"
            f"   [cyan]▸[/cyan] SESSION: {total}"
            f"   [dim]▸[/dim] HISTORY: {hist}"
        )
        self._update_retry_bar()

    def _selected_state(self) -> JobState | None:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return None
        states = self.job_manager.all_states()
        if table.cursor_row < len(states):
            return states[table.cursor_row]
        return None

    def _update_retry_bar(self):
        state     = self._selected_state()
        retry_bar = self.query_one("#retry_bar", Static)
        if state and state.status in RETRYABLE:
            label = {
                JobStatus.FAILED:    "FAILED",
                JobStatus.CANCELLED: "CANCELLED",
                JobStatus.COMPLETED: "COMPLETED",
            }.get(state.status, "")
            retry_bar.update(
                f"  [yellow]▸ [{label}] {state.name[:24]} "
                f"— sent {state.sent} · failed {state.failed}[/yellow]"
                f"   [bold green][ R — RETRY ][/bold green]"
            )
        else:
            retry_bar.update("")

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ):
        self._update_retry_bar()
        state = self._selected_state()
        if (
            state
            and state.status == JobStatus.FAILED
            and state.error_message
        ):
            self.query_one("#job_error_msg", Static).update(
                f"[red]  ✗ {state.error_message[:72]}[/red]"
            )
        else:
            self.query_one("#job_error_msg", Static).update("")

    def action_new_job(self):
        self.app.push_screen(
            NewJobScreen(self.job_manager, self.smtp_config)
        )

    def action_library(self):
        from ui.library_screen import LibraryScreen
        self.app.push_screen(LibraryScreen())

    def action_history(self):
        from ui.history_screen import HistoryScreen
        self.app.push_screen(
            HistoryScreen(self.job_manager, self.smtp_config)
        )

    def action_raffle(self):
        from ui.raffle_screen import RaffleScreen
        self.app.push_screen(
            RaffleScreen(
                smtp_config = self.smtp_config,
                job_manager = self.job_manager,
            )
        )

    def action_retry_job(self):
        state = self._selected_state()
        if not state or state.status not in RETRYABLE:
            self.query_one("#job_error_msg", Static).update(
                "[yellow]  ⚠ Select a failed/cancelled/done job[/yellow]"
            )
            return
        original_job = self.job_manager.get_job(state.job_id)
        if not original_job:
            return
        new_job = self.job_manager.create_job(original_job.config)
        self.job_manager.start_job(new_job)
        self.query_one("#job_error_msg", Static).update(
            f"[green]  ✓ Retry launched › {new_job.job_id}[/green]"
        )
        self._update_retry_bar()

    def action_cancel_job(self):
        state = self._selected_state()
        if state:
            self.job_manager.cancel_job(state.job_id)

    def action_settings(self):
        self.app.push_screen(SetupScreen())

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_new":
            self.action_new_job()
        elif event.button.id == "btn_library":
            self.action_library()
        elif event.button.id == "btn_history":
            self.action_history()
        elif event.button.id == "btn_raffle":
            self.action_raffle()
        elif event.button.id == "btn_cancel":
            self.action_cancel_job()
        elif event.button.id == "btn_settings":
            self.action_settings()
        elif event.button.id == "btn_quit":
            self.app.exit()


class VoidSendApp(App):

    CSS = """
    Screen {
        background: #0a0e0a;
    }
    Header {
        background: #0d1a0d;
        color: #00ff41;
        text-style: bold;
    }
    Footer {
        background: #0d1a0d;
        color: #1a4d1a;
    }
    #main_container {
        height: 1fr;
        padding: 0 1;
        background: #0a0e0a;
    }
    #title_bar {
        background: #0d1a0d;
        color: #00ff41;
        text-align: center;
        padding: 0 1;
        text-style: bold;
        border-bottom: solid #1a4d1a;
    }
    #status_bar {
        height: 1;
        padding: 0 1;
        background: #080c08;
        color: #00cc33;
        border-bottom: solid #0d1a0d;
    }
    #job_table {
        height: 1fr;
        border: solid #1a4d1a;
        background: #080c08;
        color: #00cc33;
    }
    DataTable > .datatable--header {
        background: #0d1a0d;
        color: #00ff41;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: #0d3d0d;
        color: #00ff41;
    }
    DataTable > .datatable--odd-row {
        background: #080c08;
    }
    DataTable > .datatable--even-row {
        background: #090d09;
    }
    #job_error_msg {
        height: 1;
        padding: 0 1;
        background: #0a0e0a;
    }
    #retry_bar {
        height: auto;
        min-height: 1;
        padding: 0 1;
        background: #0a1a0a;
        border-top: solid #1a4d1a;
        border-bottom: solid #1a4d1a;
    }
    #btn_row1 {
        height: 3;
        margin-top: 1;
        background: #0a0e0a;
    }
    #btn_row2 {
        height: 3;
        background: #0a0e0a;
    }
    #btn_row1 Button {
        width: 1fr;
        height: 3;
        margin: 0 0 0 1;
        background: #0d1a0d;
        color: #00cc33;
        border: solid #1a4d1a;
        text-style: bold;
    }
    #btn_row2 Button {
        width: 1fr;
        height: 3;
        margin: 0 0 0 1;
        background: #080c08;
        color: #1a8c1a;
        border: solid #0d2d0d;
        text-style: bold;
    }
    #btn_new {
        background: #003300 !important;
        color: #00ff41 !important;
        border: solid #00cc33 !important;
    }
    #btn_row1 Button:hover,
    #btn_row2 Button:hover {
        background: #0d3d0d;
        color: #00ff41;
        border: solid #00cc33;
    }
    #btn_cancel {
        color: #cc3300 !important;
        border: solid #441100 !important;
    }
    #btn_quit {
        color: #444444 !important;
        border: solid #222222 !important;
    }
    """

    def __init__(
        self,
        smtp_config=None,
        notification_cfg=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.smtp_config        = smtp_config
        self.notification_cfg   = notification_cfg or NotificationConfig()
        self._config_passphrase = ""
        self.job_manager        = JobManager(
            on_update=self._on_job_update
        )

    def _on_job_update(self, state: JobState):
        try:
            screen = self.screen
            if isinstance(screen, JobDashboard):
                screen.refresh_table()
        except Exception:
            pass

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

        if (
            self.notification_cfg.enabled
            and self.notification_cfg.milestones
            and state.status == JobStatus.RUNNING
        ):
            import asyncio
            pct = state.progress_pct
            for milestone in (25, 50, 75):
                if abs(pct - milestone) < 1.0:
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
