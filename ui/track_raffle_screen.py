# ui/track_raffle_screen.py
# VoidSend - Live raffle entry tracker screen

import asyncio
import time
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Static
from typing import Optional

from core.raffle import RaffleConfig, raffle_stats, load_raffle
from raffle_server.server import get_all_entries, clear_entries


class TrackRaffleScreen(Screen):
    """
    Live entry tracker for an active raffle.
    Shows every ticket submission in real time.
    Auto-refreshes every 2 seconds while open.
    """

    BINDINGS = [
        Binding("escape", "cancel",  "Back"),
        Binding("r",      "refresh", "Refresh"),
        Binding("c",      "clear",   "Clear Entries"),
        Binding("w",      "winners", "Winners Only"),
    ]

    CSS = """
    TrackRaffleScreen {
        background: #0a0e0a;
    }
    #track_titlebar {
        background: #0d1a0d;
        color: #00ff41;
        text-align: center;
        padding: 0 1;
        text-style: bold;
        border-bottom: solid #1a4d1a;
        height: 1;
    }
    #track_container {
        height: 1fr;
        padding: 0 1;
        background: #0a0e0a;
    }
    #stats_bar {
        height: 1;
        padding: 0 1;
        background: #080c08;
        color: #00cc33;
        border-bottom: solid #0d1a0d;
        margin-bottom: 1;
    }
    #url_bar {
        height: 1;
        padding: 0 1;
        color: #1a6b1a;
        margin-bottom: 1;
    }
    #entry_table {
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
    DataTable > .datatable--odd-row  { background: #080c08; }
    DataTable > .datatable--even-row { background: #090d09; }
    #track_status {
        min-height: 1;
        padding: 0 1;
        margin-top: 1;
        color: #00cc33;
    }
    #track_actions {
        height: auto;
        margin-top: 1;
        background: #0a0e0a;
    }
    #track_actions Button {
        margin: 0 1;
        min-width: 16;
        height: 3;
        background: #0d1a0d;
        color: #00cc33;
        border: solid #1a4d1a;
        text-style: bold;
    }
    #track_actions Button:hover {
        background: #0d3d0d;
        color: #00ff41;
        border: solid #00cc33;
    }
    #btn_track_back {
        color: #444444 !important;
        border: solid #222222 !important;
    }
    #btn_track_clear {
        color: #cc3300 !important;
        border: solid #441100 !important;
    }
    """

    def __init__(
        self,
        raffle: RaffleConfig,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.raffle        = raffle
        self._winners_only = False
        self._entry_count  = 0

    def compose(self) -> ComposeResult:
        yield Static(
            f"▓▒░ TRACKING: {self.raffle.name[:30]} ░▒▓",
            id="track_titlebar",
        )
        yield Container(
            Static("", id="stats_bar"),
            Static("", id="url_bar"),
            DataTable(id="entry_table"),
            Static("", id="track_status"),
            Horizontal(
                Button(
                    "Refresh [R]",
                    id="btn_track_refresh",
                    variant="default",
                ),
                Button(
                    "Winners Only [W]",
                    id="btn_track_winners",
                    variant="default",
                ),
                Button(
                    "Clear Entries [C]",
                    id="btn_track_clear",
                    variant="error",
                ),
                Button(
                    "Back [ESC]",
                    id="btn_track_back",
                    variant="default",
                ),
                id="track_actions",
            ),
            id="track_container",
        )

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns(
            "TIME", "TICKET", "EMAIL",
            "NAME", "RESULT", "IP",
        )
        self._refresh_data()
        # Auto-refresh every 2 seconds
        self.set_interval(2.0, self._refresh_data)

    def _refresh_data(self):
        """Reload entries and update table."""
        # Reload raffle for latest stats
        fresh = load_raffle(self.raffle.raffle_id)
        if fresh:
            self.raffle = fresh

        entries = get_all_entries(self.raffle.raffle_id)

        # Filter if winners only mode
        if self._winners_only:
            entries = [e for e in entries if e.get("winner")]

        # Update stats bar
        stats = raffle_stats(self.raffle)
        self.query_one("#stats_bar", Static).update(
            f"  [green]●[/green] ENTRIES: "
            f"[bold green]{len(get_all_entries(self.raffle.raffle_id))}[/bold green]"
            f"   [cyan]▸[/cyan] WINNERS CLAIMED: "
            f"[bold]{stats['claimed']}[/bold]"
            f"   [dim]▸[/dim] UNCLAIMED: {stats['unclaimed']}"
            f"   [dim]▸[/dim] PARTICIPATION: {stats['participation']}"
        )

        # Update URL bar
        verify_url = self.raffle.verify_url or "Server not started"
        self.query_one("#url_bar", Static).update(
            f"  [dim]▸ URL:[/dim] [cyan]{verify_url}[/cyan]"
        )

        # Rebuild table only if count changed
        if len(entries) == self._entry_count and entries:
            return

        self._entry_count = len(entries)
        table = self.query_one(DataTable)
        table.clear()

        if not entries:
            table.add_row(
                "", "[dim]No entries yet[/dim]",
                "", "", "", "",
            )
            self.query_one("#track_status", Static).update(
                f"[dim]  Waiting for submissions..."
                f"{'  [yellow]WINNERS ONLY MODE[/yellow]' if self._winners_only else ''}[/dim]"
            )
            return

        # Show newest first
        for entry in reversed(entries):
            ts     = entry.get("timestamp", "")[-8:]  # HH:MM:SS
            ticket = entry.get("ticket", "")
            email  = entry.get("email", "[dim]unknown[/dim]")
            name   = entry.get("name", "")[:16]
            ip     = entry.get("ip", "")[:15]

            if entry.get("winner"):
                result = "[bold green]🎉 WINNER[/bold green]"
            elif entry.get("valid"):
                result = "[dim]not winner[/dim]"
            else:
                result = "[red]invalid[/red]"

            table.add_row(ts, ticket, email, name, result, ip)

        mode = (
            "[yellow]  ⚠ WINNERS ONLY[/yellow]"
            if self._winners_only else ""
        )
        self.query_one("#track_status", Static).update(
            f"[dim]  {len(entries)} entries  ·  auto-refresh 2s[/dim]{mode}"
        )

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#track_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def action_refresh(self):
        self._refresh_data()
        self._set_status("✓ Refreshed", "green")

    def action_clear(self):
        clear_entries(self.raffle.raffle_id)
        self._entry_count = 0
        self._refresh_data()
        self._set_status("✓ Entries cleared", "yellow")

    def action_winners(self):
        self._winners_only = not self._winners_only
        self._entry_count  = 0
        self._refresh_data()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        bid = event.button.id
        if bid == "btn_track_refresh":
            self.action_refresh()
        elif bid == "btn_track_winners":
            self.action_winners()
        elif bid == "btn_track_clear":
            self.action_clear()
        elif bid == "btn_track_back":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()

    def notify_new_entry(self, entry: dict):
        """Called by server callback when new entry arrives."""
        self.call_from_thread(self._refresh_data)
