# ui/raffle_screen.py
# VoidSend - Raffle manager
# Added: tunnel, GitHub Pages deploy, entry tracking screen

import asyncio
import time
from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, DataTable, Static, Label
)
from typing import Optional

from core.raffle import (
    RaffleConfig, RaffleStatus,
    generate_tickets, save_raffle, load_raffle,
    list_raffles, delete_raffle, raffle_stats,
    get_local_ip,
)
from core.csv_reader import load_subscribers


TICKET_LENGTH_OPTIONS = [
    ("4 digits  (e.g. 4821)",      "4"),
    ("6 digits  (e.g. 482193)",    "6"),
    ("9 digits  (e.g. 482193756)", "9"),
]

STATUS_COLORS = {
    RaffleStatus.DRAFT:  "[dim]📝 Draft[/dim]",
    RaffleStatus.ACTIVE: "[bold green]▶ Active[/bold green]",
    RaffleStatus.CLOSED: "[cyan]✓ Closed[/cyan]",
}

try:
    from textual.widgets import Select
    HAS_SELECT = True
except ImportError:
    HAS_SELECT = False


class RaffleScreen(Screen):

    BINDINGS = [
        Binding("escape", "cancel",  "Back"),
        Binding("n",      "new",     "New"),
        Binding("s",      "start",   "Start"),
        Binding("t",      "track",   "Track"),
        Binding("x",      "close_r", "Close"),
        Binding("d",      "delete",  "Delete"),
    ]

    CSS = """
    RaffleScreen { background: #0a0e0a; }
    #raffle_titlebar {
        background: #0d1a0d; color: #00ff41;
        text-align: center; padding: 0 1;
        text-style: bold; border-bottom: solid #1a4d1a;
        height: 1;
    }
    #raffle_container {
        height: 1fr; padding: 0 1;
        background: #0a0e0a;
    }
    #raffle_table {
        height: 8; border: solid #1a4d1a;
        background: #080c08; color: #00cc33;
    }
    DataTable > .datatable--header {
        background: #0d1a0d; color: #00ff41;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: #0d3d0d; color: #00ff41;
    }
    #detail_panel {
        height: auto; border: solid #1a4d1a;
        padding: 0 1; margin-top: 1;
        color: #00cc33; background: #080c08;
    }
    #stats_panel {
        height: auto; border: solid #0d2d0d;
        padding: 0 1; margin-top: 1;
        color: #1a8c1a; background: #080c08;
    }
    #raffle_status {
        min-height: 1; margin-top: 1;
        padding: 0 1; color: #00cc33;
    }
    #raffle_actions { height: auto; margin-top: 1; background: #0a0e0a; }
    #raffle_actions Button {
        margin: 0 1; min-width: 12; height: 3;
        background: #0d1a0d; color: #00cc33;
        border: solid #1a4d1a; text-style: bold;
    }
    #raffle_actions2 { height: auto; background: #0a0e0a; }
    #raffle_actions2 Button {
        margin: 0 1; min-width: 12; height: 3;
        background: #080c08; color: #1a8c1a;
        border: solid #0d2d0d;
    }
    #btn_raffle_new   { background: #003300 !important; color: #00ff41 !important; border: solid #00cc33 !important; }
    #btn_raffle_track { background: #003300 !important; color: #00ff41 !important; border: solid #00cc33 !important; }
    #btn_raffle_del   { color: #cc3300 !important; border: solid #441100 !important; }
    """

    def __init__(self, smtp_config=None, job_manager=None, **kwargs):
        super().__init__(**kwargs)
        self.smtp_config  = smtp_config
        self.job_manager  = job_manager
        self._raffles:    list[RaffleConfig] = []
        self._server      = None
        self._track_screen = None

    def compose(self) -> ComposeResult:
        yield Static(
            "▓▒░ VOIDSEND RAFFLE MANAGER ░▒▓",
            id="raffle_titlebar",
        )
        yield Container(
            DataTable(id="raffle_table"),
            Static("", id="detail_panel"),
            Static("", id="stats_panel"),
            Static("", id="raffle_status"),
            Horizontal(
                Button("+ New [N]",   id="btn_raffle_new",   variant="success"),
                Button("▶ Start [S]", id="btn_raffle_start", variant="default"),
                Button("Track [T]",   id="btn_raffle_track", variant="success"),
                Button("Deploy",      id="btn_raffle_pages", variant="default"),
                id="raffle_actions",
            ),
            Horizontal(
                Button("Close [X]",   id="btn_raffle_close", variant="default"),
                Button("Delete [D]",  id="btn_raffle_del",   variant="error"),
                Button("Back",        id="btn_raffle_back",  variant="default"),
                id="raffle_actions2",
            ),
            id="raffle_container",
        )

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns(
            "ID", "NAME", "PRIZE",
            "TICKETS", "WINNERS", "STATUS", "CREATED",
        )
        self._load_table()

    def _load_table(self):
        table = self.query_one(DataTable)
        table.clear()
        self._raffles = list_raffles()

        if not self._raffles:
            table.add_row(
                "[dim]No raffles[/dim]",
                "", "", "", "", "", "",
            )
            self._set_status(
                "No raffles. Press N to create one.", "dim"
            )
            return

        for r in self._raffles:
            created    = time.strftime(
                "%m/%d %H:%M", time.localtime(r.created_at)
            )
            status_str = STATUS_COLORS.get(r.status, r.status.value)
            table.add_row(
                r.raffle_id, r.name[:18], r.prize[:18],
                str(len(r.entries)), str(r.winner_count),
                status_str, created,
            )

    def _selected_raffle(self) -> Optional[RaffleConfig]:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return None
        if table.cursor_row >= len(self._raffles):
            return None
        return self._raffles[table.cursor_row]

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#raffle_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def on_data_table_row_highlighted(
        self, event: DataTable.RowHighlighted
    ):
        raffle = self._selected_raffle()
        if not raffle:
            return
        self._show_detail(raffle)

    def _show_detail(self, raffle: RaffleConfig):
        lines = [
            f"[bold]{raffle.name}[/bold]  [{raffle.raffle_id}]",
            f"Prize  : [green]{raffle.prize}[/green]",
            f"Len    : {raffle.ticket_length} digits",
            f"URL    : [cyan]{raffle.verify_url or 'not started'}[/cyan]",
        ]
        if raffle.expiry_date:
            lines.append(f"Expires: {raffle.expiry_date}")
        self.query_one("#detail_panel", Static).update(
            "\n".join(lines)
        )

        s = raffle_stats(raffle)
        from raffle_server.server import get_all_entries
        entries = get_all_entries(raffle.raffle_id)
        self.query_one("#stats_panel", Static).update(
            f"Entries: [white]{s['total']}[/white]"
            f"  Verified: [yellow]{s['verified']}[/yellow]"
            f"  Winners: [green]{s['winners']}[/green]"
            f"  Claimed: [green]{s['claimed']}[/green]"
            f"  Attempts: [cyan]{len(entries)}[/cyan]"
        )

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_new(self):
        self.app.push_screen(
            NewRaffleScreen(
                smtp_config = self.smtp_config,
                on_created  = self._on_raffle_created,
            )
        )

    def _on_raffle_created(self, raffle: RaffleConfig):
        self._load_table()
        self._set_status(
            f"✓ '{raffle.name}' — {len(raffle.entries)} tickets", "green"
        )

    def action_start(self):
        raffle = self._selected_raffle()
        if not raffle:
            self._set_status("✗ Select a raffle first", "red")
            return
        if raffle.status == RaffleStatus.ACTIVE:
            self._set_status(
                f"Already active: {raffle.verify_url}", "yellow"
            )
            return
        asyncio.ensure_future(self._start_server(raffle))

    async def _start_server(self, raffle: RaffleConfig):
        from raffle_server.server import start_raffle_server
        from raffle_server.tunnel import (
            start_tunnel, get_tunnel_status, is_ngrok_available
        )

        self._set_status("Starting server...", "yellow")

        # Try ngrok tunnel first
        tunnel_url = ""
        if is_ngrok_available():
            self._set_status("Starting ngrok tunnel...", "yellow")
            ok, result = await start_tunnel(port=raffle.server_port)
            if ok:
                tunnel_url = result
                self._set_status(
                    f"✓ Tunnel active: {tunnel_url}", "green"
                )
            else:
                self._set_status(
                    f"Tunnel failed ({result}) — using LAN IP", "yellow"
                )

        # Fallback to LAN IP
        if not tunnel_url:
            ip         = get_local_ip()
            tunnel_url = f"http://{ip}:{raffle.server_port}/verify"

        raffle.verify_url = tunnel_url
        raffle.status     = RaffleStatus.ACTIVE
        save_raffle(raffle)

        # Get reference to track screen if open
        track_screen = self._track_screen

        def on_entry(entry: dict):
            asyncio.ensure_future(
                self._handle_entry(raffle, entry, track_screen)
            )

        def on_winner(result: dict):
            asyncio.ensure_future(
                self._notify_winner(raffle, result)
            )

        def on_verify(result: dict):
            self._load_table()
            fresh = load_raffle(raffle.raffle_id)
            if fresh:
                self._show_detail(fresh)

        self._server = await start_raffle_server(
            raffle_id  = raffle.raffle_id,
            port       = raffle.server_port,
            verify_url = tunnel_url,
            on_winner  = on_winner,
            on_verify  = on_verify,
            on_entry   = on_entry,
        )

        self._load_table()
        self._set_status(
            f"✓ Live: {tunnel_url}", "green"
        )

    async def _handle_entry(
        self,
        raffle:       RaffleConfig,
        entry:        dict,
        track_screen: Optional[object],
    ):
        """Handle every verification attempt — update tracker."""
        if track_screen:
            try:
                track_screen.notify_new_entry(entry)
            except Exception:
                pass

    async def _notify_winner(
        self, raffle: RaffleConfig, result: dict
    ):
        from core.notifier import notify_job_event
        notif_cfg = getattr(self.app, "notification_cfg", None)
        if not notif_cfg or not notif_cfg.enabled:
            return

        ticket = result.get("ticket", "")
        email  = result.get("email", "")
        name   = result.get("name", "")

        await notify_job_event(
            cfg         = notif_cfg,
            smtp_config = self.smtp_config,
            job_id      = raffle.raffle_id,
            name        = (
                f"🎉 WINNER — {raffle.name}\n"
                f"Ticket: {ticket}\n"
                f"Email:  {email}\n"
                f"Name:   {name}"
            ),
            status      = "winner verified",
            sent        = 0,
            failed      = 0,
            elapsed     = 0,
        )

    def action_track(self):
        raffle = self._selected_raffle()
        if not raffle:
            self._set_status("✗ Select a raffle first", "red")
            return
        from ui.track_raffle_screen import TrackRaffleScreen
        screen = TrackRaffleScreen(raffle=raffle)
        self._track_screen = screen
        self.app.push_screen(screen)

    def _deploy_github_pages(self):
        raffle = self._selected_raffle()
        if not raffle:
            self._set_status("✗ Select a raffle first", "red")
            return
        if not raffle.verify_url:
            self._set_status(
                "✗ Start raffle server first to get verify URL", "red"
            )
            return
        self.app.push_screen(
            DeployPagesScreen(
                raffle      = raffle,
                on_deployed = self._on_pages_deployed,
            )
        )

    def _on_pages_deployed(self, page_url: str, raffle: RaffleConfig):
        self._load_table()
        self._set_status(
            f"✓ Live on GitHub Pages: {page_url}", "green"
        )

    def action_close_r(self):
        raffle = self._selected_raffle()
        if not raffle:
            self._set_status("✗ Select a raffle first", "red")
            return
        raffle.status = RaffleStatus.CLOSED
        save_raffle(raffle)
        asyncio.ensure_future(self._stop_server(raffle.raffle_id))
        asyncio.ensure_future(self._stop_tunnel())
        self._load_table()
        self._set_status(f"✓ '{raffle.name}' closed", "yellow")

    async def _stop_server(self, raffle_id: str):
        from raffle_server.server import stop_raffle_server
        await stop_raffle_server(raffle_id)

    async def _stop_tunnel(self):
        from raffle_server.tunnel import stop_tunnel
        await stop_tunnel()

    def action_delete(self):
        raffle = self._selected_raffle()
        if not raffle:
            self._set_status("✗ Select a raffle first", "red")
            return
        if raffle.status == RaffleStatus.ACTIVE:
            self._set_status("✗ Close raffle before deleting", "red")
            return
        delete_raffle(raffle.raffle_id)
        self._load_table()
        self._set_status("✓ Deleted", "yellow")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "btn_raffle_new":
            self.action_new()
        elif bid == "btn_raffle_start":
            self.action_start()
        elif bid == "btn_raffle_track":
            self.action_track()
        elif bid == "btn_raffle_pages":
            self._deploy_github_pages()
        elif bid == "btn_raffle_close":
            self.action_close_r()
        elif bid == "btn_raffle_del":
            self.action_delete()
        elif bid == "btn_raffle_back":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()


# ── New Raffle Screen ─────────────────────────────────────────────────────────

class NewRaffleScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    NewRaffleScreen { background: #0a0e0a; }
    #nr_titlebar {
        background: #0d1a0d; color: #00ff41;
        text-align: center; padding: 0 1;
        text-style: bold; border-bottom: solid #1a4d1a;
        height: 1;
    }
    #nr_container { height: 1fr; padding: 0 1; background: #0a0e0a; }
    #nr_scroll {
        height: 1fr; border: solid #1a4d1a;
        padding: 1 2; background: #080c08;
    }
    #nr_actions { height: auto; margin-top: 1; background: #0a0e0a; }
    #nr_actions Button {
        margin: 0 1; min-width: 18; height: 3;
        background: #0d1a0d; color: #00cc33;
        border: solid #1a4d1a;
    }
    #btn_nr_generate {
        background: #003300 !important;
        color: #00ff41 !important;
        border: solid #00cc33 !important;
    }
    .field_row { height: auto; margin-bottom: 1; }
    .field_row Static {
        width: 1fr; height: 3;
        border: solid #1a4d1a; padding: 0 1;
        content-align: left middle; background: #080c08;
        color: #00cc33;
    }
    .field_row Button {
        width: 10; min-width: 10;
        margin-left: 1; height: 3;
        background: #0d1a0d; color: #00cc33;
        border: solid #1a4d1a;
    }
    Label { margin-top: 1; color: #1a8c1a; }
    #nr_status { min-height: 1; margin-top: 1; color: #00cc33; }
    """

    def __init__(
        self,
        smtp_config=None,
        on_created=None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.smtp_config   = smtp_config
        self.on_created    = on_created
        self._name         = ""
        self._prize        = ""
        self._message      = ""
        self._csv_path     = ""
        self._expiry       = ""
        self._winner_count = "1"
        self._port         = "8080"
        self._ticket_len   = "6"

    def compose(self) -> ComposeResult:
        yield Static(
            "▓▒░ NEW RAFFLE ░▒▓", id="nr_titlebar"
        )
        yield Container(
            ScrollableContainer(
                Label("Raffle Name"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_nr_name"),
                    Button("edit", id="btn_nr_name", variant="default"),
                    classes="field_row",
                ),
                Label("Prize"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_nr_prize"),
                    Button("edit", id="btn_nr_prize", variant="default"),
                    classes="field_row",
                ),
                Label("Custom Message"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_nr_msg"),
                    Button("edit", id="btn_nr_msg", variant="default"),
                    classes="field_row",
                ),
                Label("Subscriber CSV"),
                Horizontal(
                    Static("[dim]tap browse[/dim]", id="val_nr_csv"),
                    Button("browse", id="btn_nr_csv", variant="default"),
                    classes="field_row",
                ),
                Label("Ticket Length"),
                Horizontal(
                    Static("6 digits", id="val_nr_len"),
                    Button("edit", id="btn_nr_len", variant="default"),
                    classes="field_row",
                ),
                Label("Number of Winners"),
                Horizontal(
                    Static("1", id="val_nr_winners"),
                    Button("edit", id="btn_nr_winners", variant="default"),
                    classes="field_row",
                ),
                Label("Expiry Date (optional)"),
                Horizontal(
                    Static("[dim]no expiry[/dim]", id="val_nr_expiry"),
                    Button("edit", id="btn_nr_expiry", variant="default"),
                    classes="field_row",
                ),
                Label("Server Port"),
                Horizontal(
                    Static("8080", id="val_nr_port"),
                    Button("edit", id="btn_nr_port", variant="default"),
                    classes="field_row",
                ),
                Static("", id="nr_status"),
                id="nr_scroll",
            ),
            Horizontal(
                Button(
                    "Generate Tickets",
                    id="btn_nr_generate",
                    variant="success",
                ),
                Button("Cancel", id="btn_nr_cancel", variant="error"),
                id="nr_actions",
            ),
            id="nr_container",
        )

    def on_mount(self):
        self.call_after_refresh(self._scroll_top)

    def _scroll_top(self):
        try:
            self.query_one(
                "#nr_scroll", ScrollableContainer
            ).scroll_home(animate=False)
        except Exception:
            pass

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#nr_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _set_field(self, wid: str, val: str):
        try:
            self.query_one(f"#{wid}", Static).update(
                val if val else "[dim]not set[/dim]"
            )
        except Exception:
            pass

    def _edit(self, title, label, attr, wid, hint="", validator=None):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            setattr(self, attr, val)
            self._set_field(wid, val)
        self.app.push_screen(InputDialog(
            title         = title,
            label         = label,
            on_submit     = on_submit,
            initial_value = getattr(self, attr, ""),
            hint          = hint,
            validator     = validator,
        ))

    def _browse_csv(self):
        from ui.file_browser import FileBrowserScreen
        def on_picked(path: str):
            self._csv_path = path
            self._set_field("val_nr_csv", path.split("/")[-1])
            try:
                result = load_subscribers(path)
                self._set_status(
                    f"✓ {result.valid_count} subscribers", "green"
                )
            except Exception as e:
                self._set_status(f"✗ {e}", "red")
        self.app.push_screen(FileBrowserScreen(
            on_select  = on_picked,
            filter_ext = [".csv"],
            title      = "Select Subscriber CSV",
        ))

    def _edit_ticket_len(self):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            if val in ("4", "6", "9"):
                self._ticket_len = val
                self._set_field("val_nr_len", f"{val} digits")
            else:
                self._set_status("✗ Must be 4, 6, or 9", "red")
        self.app.push_screen(InputDialog(
            title     = "Ticket Length",
            label     = "Enter ticket length (4, 6, or 9):",
            on_submit = on_submit,
            hint      = "4 = 4821  ·  6 = 482193  ·  9 = 482193756",
            validator = lambda v: (
                None if v in ("4", "6", "9")
                else "Must be 4, 6, or 9"
            ),
        ))

    def _generate(self):
        errors = []
        if not self._name:
            errors.append("Raffle name required")
        if not self._prize:
            errors.append("Prize required")
        if not self._csv_path or not Path(self._csv_path).exists():
            errors.append("Valid CSV required")

        try:
            winner_count = int(self._winner_count)
            if winner_count < 1:
                errors.append("At least 1 winner required")
        except ValueError:
            errors.append("Winner count must be a number")
            winner_count = 1

        try:
            port = int(self._port)
        except ValueError:
            errors.append("Port must be a number")
            port = 8080

        if errors:
            self._set_status("✗ " + " | ".join(errors), "red")
            return

        try:
            result      = load_subscribers(self._csv_path)
            subscribers = [
                {"email": s.email, "name": s.name}
                for s in result.subscribers
            ]
            if not subscribers:
                self._set_status("✗ No valid subscribers", "red")
                return

            raffle = generate_tickets(
                subscribers   = subscribers,
                ticket_length = int(self._ticket_len),
                winner_count  = winner_count,
            )
            raffle.name        = self._name
            raffle.prize       = self._prize
            raffle.message     = self._message
            raffle.expiry_date = self._expiry or None
            raffle.server_port = port

            save_raffle(raffle)
            self._set_status(
                f"✓ {len(raffle.entries)} tickets · "
                f"{winner_count} winner(s)", "green"
            )

            if self.on_created:
                self.on_created(raffle)

            self.app.pop_screen()
            self.app.push_screen(
                RaffleSendScreen(
                    raffle      = raffle,
                    smtp_config = self.smtp_config,
                    job_manager = getattr(self.app, "job_manager", None),
                )
            )
        except Exception as e:
            self._set_status(f"✗ {e}", "red")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "btn_nr_name":
            self._edit("Raffle Name", "Enter name:", "_name", "val_nr_name",
                       hint="e.g. August Giveaway")
        elif bid == "btn_nr_prize":
            self._edit("Prize", "Describe prize:", "_prize", "val_nr_prize",
                       hint="e.g. $100 Amazon Gift Card")
        elif bid == "btn_nr_msg":
            self._edit("Message", "Custom message:", "_message", "val_nr_msg",
                       hint="Shown in email and verify page")
        elif bid == "btn_nr_csv":
            self._browse_csv()
        elif bid == "btn_nr_len":
            self._edit_ticket_len()
        elif bid == "btn_nr_winners":
            self._edit("Winners", "How many winners?",
                       "_winner_count", "val_nr_winners",
                       hint="Must be less than total subscribers")
        elif bid == "btn_nr_expiry":
            self._edit("Expiry Date", "Enter expiry (optional):",
                       "_expiry", "val_nr_expiry",
                       hint="YYYY-MM-DD e.g. 2026-12-31")
        elif bid == "btn_nr_port":
            self._edit("Server Port", "Port for verify server:",
                       "_port", "val_nr_port",
                       hint="Default 8080")
        elif bid == "btn_nr_generate":
            self._generate()
        elif bid == "btn_nr_cancel":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()


# ── Raffle Send Screen ────────────────────────────────────────────────────────

class RaffleSendScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    RaffleSendScreen { background: #0a0e0a; }
    #rs_titlebar {
        background: #0d1a0d; color: #00ff41;
        text-align: center; padding: 0 1;
        text-style: bold; border-bottom: solid #1a4d1a;
        height: 1;
    }
    #rs_container {
        height: 1fr; padding: 1 2;
        align: center middle; background: #0a0e0a;
    }
    #rs_inner {
        height: auto; border: solid #1a4d1a;
        padding: 2 3; width: 100%;
        background: #0d1a0d;
    }
    #rs_summary { color: #00cc33; margin-bottom: 2; line-height: 2; }
    .field_row { height: auto; margin-bottom: 1; }
    .field_row Static {
        width: 1fr; height: 3;
        border: solid #1a4d1a; padding: 0 1;
        content-align: left middle; background: #080c08;
        color: #00cc33;
    }
    .field_row Button {
        width: 10; min-width: 10;
        margin-left: 1; height: 3;
    }
    Label { color: #1a8c1a; margin-top: 1; }
    #rs_status { min-height: 1; margin-top: 1; color: #00cc33; }
    #rs_actions { height: auto; margin-top: 1; background: #0d1a0d; }
    #rs_actions Button {
        margin: 0 1; min-width: 18; height: 3;
        background: #0d1a0d; color: #00cc33;
        border: solid #1a4d1a;
    }
    #btn_rs_send {
        background: #003300 !important;
        color: #00ff41 !important;
        border: solid #00cc33 !important;
    }
    """

    def __init__(self, raffle, smtp_config, job_manager, **kwargs):
        super().__init__(**kwargs)
        self.raffle      = raffle
        self.smtp_config = smtp_config
        self.job_manager = job_manager
        self._send_limit = ""

    def compose(self) -> ComposeResult:
        yield Static("▓▒░ SEND RAFFLE EMAILS ░▒▓", id="rs_titlebar")
        yield Container(
            Vertical(
                Static(
                    f"Raffle  : [bold]{self.raffle.name}[/bold]\n"
                    f"Prize   : [green]{self.raffle.prize}[/green]\n"
                    f"Tickets : [cyan]{len(self.raffle.entries)}[/cyan]"
                    f" subscribers\n"
                    f"Winners : [yellow]{self.raffle.winner_count}[/yellow]"
                    f" pre-selected",
                    id="rs_summary",
                ),
                Label("Send Limit (optional — blank = all)"),
                Horizontal(
                    Static("[dim]all subscribers[/dim]", id="val_rs_limit"),
                    Button("edit", id="btn_rs_limit", variant="default"),
                    classes="field_row",
                ),
                Static("", id="rs_status"),
                Horizontal(
                    Button("✉ Send Emails", id="btn_rs_send", variant="success"),
                    Button("Skip",          id="btn_rs_skip", variant="default"),
                    id="rs_actions",
                ),
                id="rs_inner",
            ),
            id="rs_container",
        )

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#rs_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _edit_limit(self):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            val = val.strip()
            self._send_limit = val
            try:
                w = self.query_one("#val_rs_limit", Static)
                if val:
                    effective = min(int(val), len(self.raffle.entries))
                    w.update(f"first {effective} of {len(self.raffle.entries)}")
                else:
                    w.update("[dim]all subscribers[/dim]")
            except Exception:
                pass

        def validate(val: str):
            if not val:
                return None
            try:
                n = int(val)
                if n < 1:
                    return "Must be at least 1"
                if n > len(self.raffle.entries):
                    return f"Max is {len(self.raffle.entries)}"
            except ValueError:
                return "Must be a whole number"

        self.app.push_screen(InputDialog(
            title         = "Send Limit",
            label         = "Max raffle emails to send:",
            on_submit     = on_submit,
            initial_value = self._send_limit,
            hint          = (
                f"Total: {len(self.raffle.entries)} subscribers\n"
                "Leave blank to send to everyone."
            ),
            validator     = validate,
        ))

    def _send_emails(self):
        if not self.smtp_config:
            self._set_status("✗ No SMTP config", "red")
            return
        if not self.job_manager:
            self._set_status("✗ Job manager unavailable", "red")
            return
        try:
            self._create_job()
        except Exception as e:
            self._set_status(f"✗ {e}", "red")

    def _create_job(self):
        import csv
        from pathlib import Path as P
        from core.job_manager import JobConfig

        send_limit = None
        if self._send_limit:
            try:
                send_limit = int(self._send_limit)
            except ValueError:
                pass

        entries = self.raffle.entries
        if send_limit and send_limit < len(entries):
            entries = entries[:send_limit]

        tmp_csv = (
            P.home() / ".voidsend"
            / f"raffle_{self.raffle.raffle_id}.csv"
        )
        tmp_csv.parent.mkdir(parents=True, exist_ok=True)

        with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "email", "name", "ticket",
                "raffle_name", "raffle_prize",
                "raffle_message", "verify_url", "expiry_date",
            ])
            writer.writeheader()
            for entry in entries:
                writer.writerow({
                    "email":          entry.email,
                    "name":           entry.name,
                    "ticket":         entry.ticket,
                    "raffle_name":    self.raffle.name,
                    "raffle_prize":   self.raffle.prize,
                    "raffle_message": self.raffle.message,
                    "verify_url":     (
                        self.raffle.verify_url
                        or f"http://YOUR_IP:{self.raffle.server_port}/verify"
                    ),
                    "expiry_date":    self.raffle.expiry_date or "",
                })

        template_path = (
            P(__file__).parent.parent
            / "templates" / "layouts" / "raffle.html"
        )
        if not template_path.exists():
            self._set_status("✗ raffle.html template missing", "red")
            return

        cfg = JobConfig(
            name               = f"Raffle: {self.raffle.name}",
            csv_path           = str(tmp_csv),
            html_template_path = str(template_path),
            subject_template   = f"🎟 Your ticket for {self.raffle.name}",
            smtp_config        = self.smtp_config,
            max_connections    = 3,
            delay_seconds      = 0.5,
            append_unsubscribe = False,
        )

        job = self.job_manager.create_job(cfg)
        self.job_manager.start_job(job)

        note = (
            f" (first {len(entries)} of {len(self.raffle.entries)})"
            if send_limit else ""
        )
        self._set_status(
            f"✓ Job {job.job_id} launched — "
            f"{len(entries)} emails{note}",
            "green",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "btn_rs_limit":
            self._edit_limit()
        elif event.button.id == "btn_rs_send":
            self._send_emails()
        elif event.button.id == "btn_rs_skip":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()


# ── GitHub Pages Deploy Screen ────────────────────────────────────────────────

class DeployPagesScreen(Screen):
    """Deploy verify.html to GitHub Pages with raffle config injected."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    DeployPagesScreen { background: #0a0e0a; }
    #dp_titlebar {
        background: #0d1a0d; color: #00ff41;
        text-align: center; padding: 0 1;
        text-style: bold; border-bottom: solid #1a4d1a;
        height: 1;
    }
    #dp_container {
        height: 1fr; padding: 1 2;
        align: center middle; background: #0a0e0a;
    }
    #dp_inner {
        height: auto; border: solid #1a4d1a;
        padding: 2 3; width: 100%;
        background: #0d1a0d;
    }
    #dp_info { color: #1a8c1a; margin-bottom: 2; line-height: 2; }
    .field_row { height: auto; margin-bottom: 1; }
    .field_row Static {
        width: 1fr; height: 3;
        border: solid #1a4d1a; padding: 0 1;
        content-align: left middle; background: #080c08;
        color: #00cc33;
    }
    .field_row Button {
        width: 10; min-width: 10;
        margin-left: 1; height: 3;
    }
    Label { color: #1a8c1a; margin-top: 1; }
    #dp_status { min-height: 2; margin-top: 1; color: #00cc33; }
    #dp_actions { height: auto; margin-top: 1; }
    #dp_actions Button {
        margin: 0 1; min-width: 18; height: 3;
        background: #0d1a0d; color: #00cc33;
        border: solid #1a4d1a;
    }
    #btn_dp_deploy {
        background: #003300 !important;
        color: #00ff41 !important;
        border: solid #00cc33 !important;
    }
    """

    def __init__(self, raffle, on_deployed=None, **kwargs):
        super().__init__(**kwargs)
        self.raffle      = raffle
        self.on_deployed = on_deployed
        self._token      = ""
        self._repo       = ""
        self._path       = "raffle/index.html"

    def compose(self) -> ComposeResult:
        yield Static("▓▒░ DEPLOY TO GITHUB PAGES ░▒▓", id="dp_titlebar")
        yield Container(
            Vertical(
                Static(
                    "Deploy the raffle verify page to GitHub Pages.\n"
                    "Subscribers worldwide can then verify their tickets.\n"
                    "Verify URL must be set (start server first).",
                    id="dp_info",
                ),
                Label("GitHub Personal Access Token"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_dp_token"),
                    Button("edit", id="btn_dp_token", variant="default"),
                    classes="field_row",
                ),
                Label("Repository (owner/repo)"),
                Horizontal(
                    Static(
                        "[dim]e.g. rarebyteforge/voidsend[/dim]",
                        id="val_dp_repo",
                    ),
                    Button("edit", id="btn_dp_repo", variant="default"),
                    classes="field_row",
                ),
                Label("Deploy Path"),
                Horizontal(
                    Static("raffle/index.html", id="val_dp_path"),
                    Button("edit", id="btn_dp_path", variant="default"),
                    classes="field_row",
                ),
                Static("", id="dp_status"),
                Horizontal(
                    Button("🚀 Deploy", id="btn_dp_deploy", variant="success"),
                    Button("Cancel",   id="btn_dp_cancel", variant="error"),
                    id="dp_actions",
                ),
                id="dp_inner",
            ),
            id="dp_container",
        )

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#dp_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _set_field(self, wid: str, val: str):
        try:
            self.query_one(f"#{wid}", Static).update(
                val if val else "[dim]not set[/dim]"
            )
        except Exception:
            pass

    def _edit(self, title, label, attr, wid, hint="", password=False):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            setattr(self, attr, val)
            display = ("•" * min(len(val), 12)) if password else val
            self._set_field(wid, display)
        self.app.push_screen(InputDialog(
            title         = title,
            label         = label,
            on_submit     = on_submit,
            initial_value = getattr(self, attr, ""),
            hint          = hint,
            password      = password,
        ))

    def _deploy(self):
        if not self._token:
            self._set_status("✗ GitHub token required", "red")
            return
        if not self._repo or "/" not in self._repo:
            self._set_status("✗ Repo must be owner/repo format", "red")
            return
        if not self.raffle.verify_url:
            self._set_status(
                "✗ Start raffle server first to get verify URL", "red"
            )
            return

        self._set_status("🚀 Deploying to GitHub Pages...", "yellow")
        asyncio.ensure_future(self._do_deploy())

    async def _do_deploy(self):
        from raffle_server.github_pages import deploy_to_github_pages

        ok, result = await deploy_to_github_pages(
            github_token = self._token,
            repo         = self._repo,
            raffle_name  = self.raffle.name,
            raffle_prize = self.raffle.prize,
            ticket_len   = self.raffle.ticket_length,
            verify_url   = self.raffle.verify_url,
            raffle_id    = self.raffle.raffle_id,
            expiry       = self.raffle.expiry_date or "",
            path         = self._path,
        )

        if ok:
            self._set_status(
                f"✓ Live at: {result}\n"
                f"  Share this URL with your subscribers!",
                "green",
            )
            if self.on_deployed:
                self.on_deployed(result, self.raffle)
        else:
            self._set_status(f"✗ Deploy failed: {result}", "red")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "btn_dp_token":
            self._edit(
                "GitHub Token",
                "Enter Personal Access Token:",
                "_token", "val_dp_token",
                hint="github.com/settings/tokens → repo + pages scopes",
                password=True,
            )
        elif bid == "btn_dp_repo":
            self._edit(
                "Repository",
                "Enter repo (owner/name):",
                "_repo", "val_dp_repo",
                hint="e.g. rarebyteforge/voidsend",
            )
        elif bid == "btn_dp_path":
            self._edit(
                "Deploy Path",
                "File path in repo:",
                "_path", "val_dp_path",
                hint="e.g. raffle/index.html",
            )
        elif bid == "btn_dp_deploy":
            self._deploy()
        elif bid == "btn_dp_cancel":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()
