# ui/raffle_screen.py
# VoidSend - Raffle setup and management TUI screen
# Added: send_limit support in RaffleSendScreen

import asyncio
import time
from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Header, Footer,
    DataTable, Static, Label, Select
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
    RaffleStatus.ACTIVE: "[green]▶ Active[/green]",
    RaffleStatus.CLOSED: "[blue]✓ Closed[/blue]",
}


class RaffleScreen(Screen):

    BINDINGS = [
        Binding("escape", "cancel",  "Back"),
        Binding("n",      "new",     "New Raffle"),
        Binding("s",      "start",   "Start"),
        Binding("x",      "close_r", "Close"),
        Binding("d",      "delete",  "Delete"),
    ]

    CSS = """
    #raffle_container {
        height: 1fr;
        padding: 1 2;
    }
    #raffle_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 1;
    }
    #raffle_table {
        height: 8;
        border: solid $accent;
    }
    #detail_panel {
        height: auto;
        border: solid $panel;
        padding: 1 2;
        margin-top: 1;
    }
    #stats_panel {
        height: auto;
        border: solid $panel;
        padding: 1 2;
        margin-top: 1;
    }
    #raffle_status {
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
        min-width: 14;
        height: 3;
    }
    """

    def __init__(self, smtp_config=None, job_manager=None, **kwargs):
        super().__init__(**kwargs)
        self.smtp_config = smtp_config
        self.job_manager = job_manager
        self._raffles: list[RaffleConfig] = []
        self._server = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            Static("🎟  Raffle Manager", id="raffle_title"),
            DataTable(id="raffle_table"),
            Static("", id="detail_panel"),
            Static("", id="stats_panel"),
            Static("", id="raffle_status"),
            Horizontal(
                Button("+ New [N]",   id="btn_new",    variant="success"),
                Button("▶ Start [S]", id="btn_start",  variant="default"),
                Button("✓ Close [X]", id="btn_close",  variant="default"),
                Button("Delete [D]",  id="btn_delete", variant="error"),
                Button("Back",        id="btn_back",   variant="default"),
                id="action_bar",
            ),
            id="raffle_container",
        )
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns(
            "ID", "Name", "Prize",
            "Tickets", "Winners", "Status", "Created",
        )
        self._load_table()

    def _load_table(self):
        table = self.query_one(DataTable)
        table.clear()
        self._raffles = list_raffles()

        if not self._raffles:
            table.add_row(
                "[dim]No raffles yet[/dim]",
                "", "", "", "", "", "",
            )
            self._set_status(
                "No raffles found. Press N to create one.", "dim"
            )
            return

        for r in self._raffles:
            created    = time.strftime(
                "%m/%d %H:%M", time.localtime(r.created_at)
            )
            status_str = STATUS_COLORS.get(r.status, r.status.value)
            table.add_row(
                r.raffle_id,
                r.name[:20],
                r.prize[:20],
                str(len(r.entries)),
                str(r.winner_count),
                status_str,
                created,
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
        detail = self.query_one("#detail_panel", Static)
        stats  = self.query_one("#stats_panel", Static)

        lines = [
            f"[bold]{raffle.name}[/bold]  [{raffle.raffle_id}]",
            f"Prize      : [green]{raffle.prize}[/green]",
            f"Ticket len : {raffle.ticket_length} digits",
            f"Verify URL : [cyan]{raffle.verify_url or 'not set — start to activate'}[/cyan]",
        ]
        if raffle.expiry_date:
            lines.append(f"Expires    : {raffle.expiry_date}")
        detail.update("\n".join(lines))

        s = raffle_stats(raffle)
        stats.update(
            f"Entries: [white]{s['total']}[/white]  "
            f"Verified: [yellow]{s['verified']}[/yellow]  "
            f"Winners: [green]{s['winners']}[/green]  "
            f"Claimed: [green]{s['claimed']}[/green]  "
            f"Unclaimed: [red]{s['unclaimed']}[/red]  "
            f"Participation: [cyan]{s['participation']}[/cyan]"
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
            f"✓ Raffle '{raffle.name}' created with "
            f"{len(raffle.entries)} tickets",
            "green",
        )

    def action_start(self):
        raffle = self._selected_raffle()
        if not raffle:
            self._set_status("✗ Select a raffle first", "red")
            return
        if raffle.status == RaffleStatus.ACTIVE:
            self._set_status("Already active", "yellow")
            return
        asyncio.ensure_future(self._start_server(raffle))

    async def _start_server(self, raffle: RaffleConfig):
        from raffle_server.server import start_raffle_server

        ip  = get_local_ip()
        url = f"http://{ip}:{raffle.server_port}/verify"

        raffle.verify_url = url
        raffle.status     = RaffleStatus.ACTIVE
        save_raffle(raffle)

        def on_winner(result: dict):
            asyncio.ensure_future(
                self._notify_winner(raffle, result)
            )

        def on_verify(result: dict):
            self._load_table()
            raffle_reloaded = load_raffle(raffle.raffle_id)
            if raffle_reloaded:
                self._show_detail(raffle_reloaded)

        self._server = await start_raffle_server(
            raffle_id = raffle.raffle_id,
            port      = raffle.server_port,
            on_winner = on_winner,
            on_verify = on_verify,
        )

        self._load_table()
        self._set_status(
            f"✓ Server running — share URL with subscribers: "
            f"[cyan]{url}[/cyan]",
            "green",
        )

    async def _notify_winner(
        self, raffle: RaffleConfig, result: dict
    ):
        from core.notifier import notify_job_event
        notif_cfg = getattr(self.app, "notification_cfg", None)
        if not notif_cfg or not notif_cfg.enabled:
            return
        await notify_job_event(
            cfg         = notif_cfg,
            smtp_config = self.smtp_config,
            job_id      = raffle.raffle_id,
            name        = f"🎉 Raffle Winner — {raffle.name}",
            status      = (
                f"Ticket {result.get('ticket','')} — "
                f"{result.get('email','')}"
            ),
            sent        = 0,
            failed      = 0,
            elapsed     = 0,
        )

    def action_close_r(self):
        raffle = self._selected_raffle()
        if not raffle:
            self._set_status("✗ Select a raffle first", "red")
            return
        raffle.status = RaffleStatus.CLOSED
        save_raffle(raffle)
        asyncio.ensure_future(self._stop_server(raffle.raffle_id))
        self._load_table()
        self._set_status(
            f"✓ Raffle '{raffle.name}' closed", "yellow"
        )

    async def _stop_server(self, raffle_id: str):
        from raffle_server.server import stop_raffle_server
        await stop_raffle_server(raffle_id)

    def action_delete(self):
        raffle = self._selected_raffle()
        if not raffle:
            self._set_status("✗ Select a raffle first", "red")
            return
        if raffle.status == RaffleStatus.ACTIVE:
            self._set_status(
                "✗ Close raffle before deleting", "red"
            )
            return
        delete_raffle(raffle.raffle_id)
        self._load_table()
        self._set_status("✓ Raffle deleted", "yellow")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_new":
            self.action_new()
        elif event.button.id == "btn_start":
            self.action_start()
        elif event.button.id == "btn_close":
            self.action_close_r()
        elif event.button.id == "btn_delete":
            self.action_delete()
        elif event.button.id == "btn_back":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()


# ── New Raffle Creation Screen ────────────────────────────────────────────────

class NewRaffleScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    #new_raffle_container {
        height: 1fr;
        padding: 1 2;
    }
    #new_raffle_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 1;
    }
    #new_raffle_scroll {
        height: 1fr;
        border: solid $accent;
        padding: 1 2;
    }
    #new_raffle_actions {
        height: auto;
        margin-top: 1;
        padding: 1 0;
    }
    #new_raffle_actions Button {
        margin: 0 1;
        min-width: 16;
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
    Label { margin-top: 1; }
    Select { margin-bottom: 1; }
    #new_raffle_status { min-height: 1; margin-top: 1; }
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
        yield Header()
        yield Container(
            Static("🎟  Create New Raffle", id="new_raffle_title"),
            ScrollableContainer(
                Label("Raffle Name"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_rname"),
                    Button("edit", id="btn_edit_rname", variant="default"),
                    classes="field_row",
                ),
                Label("Prize Description"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_prize"),
                    Button("edit", id="btn_edit_prize", variant="default"),
                    classes="field_row",
                ),
                Label("Custom Message (shown in email + verify page)"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_message"),
                    Button("edit", id="btn_edit_message", variant="default"),
                    classes="field_row",
                ),
                Label("Subscriber CSV"),
                Horizontal(
                    Static("[dim]tap browse[/dim]", id="val_csv"),
                    Button("browse", id="btn_browse_csv", variant="default"),
                    classes="field_row",
                ),
                Label("Ticket Length"),
                Select(
                    options=TICKET_LENGTH_OPTIONS,
                    id="ticket_len_select",
                    value="6",
                ),
                Label("Number of Winners"),
                Horizontal(
                    Static("1", id="val_winners"),
                    Button("edit", id="btn_edit_winners", variant="default"),
                    classes="field_row",
                ),
                Label("Expiry Date (optional, e.g. 2026-12-31)"),
                Horizontal(
                    Static("[dim]no expiry[/dim]", id="val_expiry"),
                    Button("edit", id="btn_edit_expiry", variant="default"),
                    classes="field_row",
                ),
                Label("Server Port"),
                Horizontal(
                    Static("8080", id="val_port"),
                    Button("edit", id="btn_edit_port", variant="default"),
                    classes="field_row",
                ),
                Static("", id="new_raffle_status"),
                id="new_raffle_scroll",
            ),
            Horizontal(
                Button(
                    "Generate Tickets",
                    id="btn_generate",
                    variant="success",
                ),
                Button("Cancel", id="btn_cancel", variant="error"),
                id="new_raffle_actions",
            ),
            id="new_raffle_container",
        )
        yield Footer()

    def on_mount(self):
        self.call_after_refresh(self._scroll_top)

    def _scroll_top(self):
        try:
            self.query_one(
                "#new_raffle_scroll", ScrollableContainer
            ).scroll_home(animate=False)
        except Exception:
            pass

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "ticket_len_select":
            self._ticket_len = str(event.value)

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#new_raffle_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _set_field(self, wid: str, val: str):
        try:
            w = self.query_one(f"#{wid}", Static)
            w.update(val if val else "[dim]not set[/dim]")
        except Exception:
            pass

    def _edit(
        self, title, label, attr, wid,
        hint="", validator=None
    ):
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
            self._set_field("val_csv", path.split("/")[-1])
            try:
                result = load_subscribers(path)
                self._set_status(
                    f"✓ {result.valid_count} subscribers loaded",
                    "green",
                )
            except Exception as e:
                self._set_status(f"✗ CSV error: {e}", "red")
        self.app.push_screen(FileBrowserScreen(
            on_select  = on_picked,
            filter_ext = [".csv"],
            title      = "Select Subscriber CSV",
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
                self._set_status(
                    "✗ No valid subscribers in CSV", "red"
                )
                return

            ticket_len = int(self._ticket_len)
            raffle     = generate_tickets(
                subscribers   = subscribers,
                ticket_length = ticket_len,
                winner_count  = winner_count,
            )

            raffle.name        = self._name
            raffle.prize       = self._prize
            raffle.message     = self._message
            raffle.expiry_date = self._expiry or None
            raffle.server_port = port

            save_raffle(raffle)

            self._set_status(
                f"✓ Generated {len(raffle.entries)} tickets "
                f"with {winner_count} winner(s)",
                "green",
            )

            if self.on_created:
                self.on_created(raffle)

            self.app.pop_screen()
            self.app.push_screen(
                RaffleSendScreen(
                    raffle      = raffle,
                    smtp_config = self.smtp_config,
                    job_manager = getattr(
                        self.app, "job_manager", None
                    ),
                )
            )

        except Exception as e:
            self._set_status(f"✗ Error: {e}", "red")

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "btn_edit_rname":
            self._edit(
                "Raffle Name", "Enter raffle name:",
                "_name", "val_rname",
                hint="e.g. August Newsletter Giveaway",
            )
        elif bid == "btn_edit_prize":
            self._edit(
                "Prize", "Describe the prize:",
                "_prize", "val_prize",
                hint="e.g. $100 Amazon Gift Card",
            )
        elif bid == "btn_edit_message":
            self._edit(
                "Custom Message",
                "Message shown in email and verify page:",
                "_message", "val_message",
                hint="e.g. Good luck! Winners contacted within 48hrs.",
            )
        elif bid == "btn_browse_csv":
            self._browse_csv()
        elif bid == "btn_edit_winners":
            self._edit(
                "Number of Winners",
                "How many winners?",
                "_winner_count", "val_winners",
                hint="Must be less than total subscribers",
            )
        elif bid == "btn_edit_expiry":
            self._edit(
                "Expiry Date",
                "Enter expiry date (optional):",
                "_expiry", "val_expiry",
                hint="Format: YYYY-MM-DD e.g. 2026-12-31",
            )
        elif bid == "btn_edit_port":
            self._edit(
                "Server Port",
                "Port for verification server:",
                "_port", "val_port",
                hint="Default 8080. Change if port is in use.",
            )
        elif bid == "btn_generate":
            self._generate()
        elif bid == "btn_cancel":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()


# ── Raffle Send Screen ────────────────────────────────────────────────────────

class RaffleSendScreen(Screen):
    """Confirm and send raffle emails with optional send limit."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    #send_container {
        height: 1fr;
        padding: 2 3;
        align: center middle;
    }
    #send_inner {
        height: auto;
        border: solid $accent;
        padding: 2 3;
        width: 100%;
    }
    #send_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 2;
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
    #send_status { min-height: 1; margin-top: 1; }
    #send_actions {
        height: auto;
        margin-top: 1;
    }
    #send_actions Button {
        margin: 0 1;
        min-width: 18;
        height: 3;
    }
    Label { margin-top: 1; }
    """

    def __init__(
        self,
        raffle:      RaffleConfig,
        smtp_config,
        job_manager,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.raffle      = raffle
        self.smtp_config = smtp_config
        self.job_manager = job_manager
        self._send_limit = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Vertical(
                Static(
                    "✉  Send Raffle Emails",
                    id="send_title",
                ),
                Static(
                    f"Raffle  : [bold]{self.raffle.name}[/bold]\n"
                    f"Prize   : [green]{self.raffle.prize}[/green]\n"
                    f"Tickets : [cyan]{len(self.raffle.entries)}[/cyan]"
                    f" subscribers\n"
                    f"Winners : [yellow]{self.raffle.winner_count}[/yellow]"
                    f" pre-selected\n\n"
                    f"Each subscriber gets a personalized email\n"
                    f"with their unique ticket number + verify link.",
                    id="send_summary",
                ),

                # ── Send limit ────────────────────────────────────────────
                Label(
                    "Send Limit (optional — blank = send all)"
                ),
                Horizontal(
                    Static(
                        "[dim]all subscribers[/dim]",
                        id="val_send_limit",
                    ),
                    Button(
                        "edit",
                        id="btn_edit_limit",
                        variant="default",
                    ),
                    classes="field_row",
                ),

                Static("", id="send_status"),
                Horizontal(
                    Button(
                        "✉ Send Raffle Emails",
                        id="btn_send",
                        variant="success",
                    ),
                    Button(
                        "Skip for now",
                        id="btn_skip",
                        variant="default",
                    ),
                    id="send_actions",
                ),
                id="send_inner",
            ),
            id="send_container",
        )
        yield Footer()

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#send_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _edit_limit(self):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            val = val.strip()
            self._send_limit = val
            try:
                w = self.query_one("#val_send_limit", Static)
                if val:
                    effective = min(
                        int(val), len(self.raffle.entries)
                    )
                    w.update(
                        f"first {effective} of "
                        f"{len(self.raffle.entries)} subscribers"
                    )
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
                    return (
                        f"Max is {len(self.raffle.entries)} "
                        f"(total subscribers)"
                    )
            except ValueError:
                return "Must be a whole number or leave blank"

        self.app.push_screen(InputDialog(
            title         = "Send Limit",
            label         = "Max raffle emails to send:",
            on_submit     = on_submit,
            initial_value = self._send_limit,
            hint          = (
                f"Total subscribers: {len(self.raffle.entries)}\n"
                "Leave blank to send to everyone.\n"
                "Useful if near daily SMTP limit."
            ),
            validator     = validate,
        ))

    def _send_emails(self):
        if not self.smtp_config:
            self._set_status(
                "✗ No SMTP config. Go to Settings first.", "red"
            )
            return
        if not self.job_manager:
            self._set_status("✗ Job manager not available.", "red")
            return

        try:
            self._create_raffle_job()
        except Exception as e:
            self._set_status(f"✗ Error: {e}", "red")

    def _create_raffle_job(self):
        import csv
        from pathlib import Path as P
        from core.job_manager import JobConfig

        # Parse send limit
        send_limit = None
        if self._send_limit:
            try:
                send_limit = int(self._send_limit)
            except ValueError:
                pass

        # Write temp CSV
        tmp_csv = (
            P.home() / ".voidsend"
            / f"raffle_{self.raffle.raffle_id}.csv"
        )
        tmp_csv.parent.mkdir(parents=True, exist_ok=True)

        entries = self.raffle.entries
        # Apply send limit to entries if set
        if send_limit and send_limit < len(entries):
            entries = entries[:send_limit]

        with open(tmp_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "email", "name", "ticket",
                    "raffle_name", "raffle_prize",
                    "raffle_message", "verify_url",
                    "expiry_date",
                ],
            )
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
                        or f"http://YOUR_IP:"
                           f"{self.raffle.server_port}/verify"
                    ),
                    "expiry_date":    self.raffle.expiry_date or "",
                })

        template_path = (
            P(__file__).parent.parent
            / "templates" / "layouts" / "raffle.html"
        )

        if not template_path.exists():
            self._set_status(
                "✗ raffle.html template not found", "red"
            )
            return

        cfg = JobConfig(
            name               = f"Raffle: {self.raffle.name}",
            csv_path           = str(tmp_csv),
            html_template_path = str(template_path),
            subject_template   = (
                f"🎟 Your ticket for {self.raffle.name}"
            ),
            smtp_config        = self.smtp_config,
            max_connections    = 3,
            delay_seconds      = 0.5,
            append_unsubscribe = False,
            send_limit         = None,  # already sliced above
        )

        job = self.job_manager.create_job(cfg)
        self.job_manager.start_job(job)

        limit_note = (
            f" (first {len(entries)} of "
            f"{len(self.raffle.entries)})"
            if send_limit else ""
        )
        self._set_status(
            f"✓ Job {job.job_id} launched — "
            f"{len(entries)} raffle emails sending{limit_note}!",
            "green",
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_edit_limit":
            self._edit_limit()
        elif event.button.id == "btn_send":
            self._send_emails()
        elif event.button.id == "btn_skip":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()
