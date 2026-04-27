# ui/subscriber_manager.py
# VoidSend - Inline subscriber manager
# Add, remove, search subscribers without editing CSV files directly.
# Persists to ~/.voidsend/subscribers.json
# Can import from CSV and export back to CSV.

import csv
import json
import time
from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Header, Footer,
    DataTable, Static, Label
)
from typing import Optional, Callable

SUBS_FILE = Path.home() / ".voidsend" / "subscribers.json"


# ── Data model ────────────────────────────────────────────────────────────────

def _load_all() -> list[dict]:
    if not SUBS_FILE.exists():
        return []
    try:
        with open(SUBS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_all(subs: list[dict]):
    SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SUBS_FILE, "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=2)


def add_subscriber(email: str, name: str = "", **extra) -> bool:
    """Add subscriber. Returns False if email already exists."""
    subs = _load_all()
    if any(s["email"].lower() == email.lower() for s in subs):
        return False
    subs.append({
        "email":      email.strip().lower(),
        "name":       name.strip(),
        "added_at":   time.strftime("%Y-%m-%d %H:%M:%S"),
        **extra,
    })
    _save_all(subs)
    return True


def remove_subscriber(email: str) -> bool:
    subs = _load_all()
    new  = [s for s in subs if s["email"].lower() != email.lower()]
    if len(new) == len(subs):
        return False
    _save_all(new)
    return True


def remove_subscribers(emails: list[str]) -> int:
    """Remove multiple subscribers. Returns count removed."""
    email_set = {e.lower() for e in emails}
    subs      = _load_all()
    new       = [s for s in subs if s["email"].lower() not in email_set]
    removed   = len(subs) - len(new)
    _save_all(new)
    return removed


def search_subscribers(query: str) -> list[dict]:
    q    = query.lower().strip()
    subs = _load_all()
    if not q:
        return subs
    return [
        s for s in subs
        if q in s["email"].lower() or q in s.get("name", "").lower()
    ]


def import_from_csv(csv_path: str) -> tuple[int, int]:
    """
    Import subscribers from CSV.
    Returns (imported, skipped_duplicates).
    """
    from core.csv_reader import load_subscribers
    result   = load_subscribers(csv_path)
    imported = 0
    skipped  = 0
    for sub in result.subscribers:
        ok = add_subscriber(
            email = sub.email,
            name  = sub.name,
            **sub.custom_fields,
        )
        if ok:
            imported += 1
        else:
            skipped += 1
    return imported, skipped


def export_to_csv(csv_path: str, emails: Optional[list[str]] = None) -> int:
    """
    Export subscribers to CSV.
    emails: if provided, only export these emails.
    Returns count exported.
    """
    subs = _load_all()
    if emails:
        email_set = {e.lower() for e in emails}
        subs      = [s for s in subs if s["email"].lower() in email_set]

    if not subs:
        return 0

    # Collect all field names
    fields = ["email", "name"]
    extra  = set()
    for s in subs:
        extra.update(k for k in s if k not in ("email", "name", "added_at"))
    fields += sorted(extra)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for s in subs:
            writer.writerow({k: s.get(k, "") for k in fields})

    return len(subs)


def get_selected_csv(emails: list[str]) -> str:
    """
    Write selected subscribers to a temp CSV and return path.
    Used by new job screen to pass selected list to mailer.
    """
    tmp = Path.home() / ".voidsend" / "selected_subscribers.csv"
    export_to_csv(str(tmp), emails)
    return str(tmp)


def get_all_csv() -> str:
    """Write all subscribers to temp CSV and return path."""
    tmp = Path.home() / ".voidsend" / "all_subscribers.csv"
    export_to_csv(str(tmp))
    return str(tmp)


# ── Screen ────────────────────────────────────────────────────────────────────

class SubscriberManager(Screen):
    """
    Full subscriber manager.
    on_select(csv_path, count) called when user confirms selection.
    If on_select is None, runs in standalone management mode.
    """

    BINDINGS = [
        Binding("escape", "cancel",     "Back"),
        Binding("a",      "add",        "Add"),
        Binding("d",      "delete_sel", "Delete"),
        Binding("s",      "search",     "Search"),
        Binding("ctrl+a", "select_all", "Select All"),
    ]

    CSS = """
    #sub_container {
        height: 1fr;
        padding: 1 2;
    }
    #sub_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 1;
    }
    #search_bar {
        height: 1;
        padding: 0 1;
        margin-bottom: 1;
        color: $accent;
    }
    #sub_table {
        height: 1fr;
        border: solid $accent;
    }
    #sub_status {
        min-height: 1;
        margin-top: 1;
        padding: 0 1;
    }
    #sub_actions {
        height: auto;
        margin-top: 1;
        padding: 1 0;
    }
    #sub_actions Button {
        margin: 0 1;
        min-width: 14;
        height: 3;
    }
    #sub_actions2 {
        height: auto;
        margin-top: 0;
        padding: 0;
    }
    #sub_actions2 Button {
        margin: 0 1;
        min-width: 14;
        height: 3;
    }
    """

    def __init__(
        self,
        on_select: Optional[Callable[[str, int], None]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.on_select     = on_select
        self._all_subs:    list[dict] = []
        self._filtered:    list[dict] = []
        self._selected:    set[str]   = set()
        self._search_query = ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(
                "👥  Subscriber Manager",
                id="sub_title",
            ),
            Static("", id="search_bar"),
            DataTable(id="sub_table", cursor_type="row"),
            Static("", id="sub_status"),

            # ── Row 1 ─────────────────────────────────────────────────────
            Horizontal(
                Button("+ Add [A]",      id="btn_add",        variant="success"),
                Button("Search [S]",     id="btn_search",     variant="default"),
                Button("Select All",     id="btn_select_all", variant="default"),
                Button("Clear Sel",      id="btn_clear_sel",  variant="default"),
                id="sub_actions",
            ),

            # ── Row 2 ─────────────────────────────────────────────────────
            Horizontal(
                Button("Delete Sel [D]", id="btn_delete",     variant="error"),
                Button("Import CSV",     id="btn_import",     variant="default"),
                Button("Export CSV",     id="btn_export",     variant="default"),
                Button(
                    "✓ Use Selected" if self.on_select else "Back",
                    id="btn_use",
                    variant="success" if self.on_select else "default",
                ),
                id="sub_actions2",
            ),
            id="sub_container",
        )
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns(
            "✓", "EMAIL", "NAME", "ADDED",
        )
        self._reload()

    def _reload(self, query: str = ""):
        self._search_query = query
        self._all_subs     = _load_all()
        self._filtered     = search_subscribers(query) if query else list(self._all_subs)

        table = self.query_one(DataTable)
        table.clear()

        if not self._filtered:
            table.add_row(
                "", "[dim]No subscribers[/dim]", "", ""
            )
            self._set_status(
                f"0 subscribers"
                + (f" matching '{query}'" if query else ""),
                "dim",
            )
            return

        for sub in self._filtered:
            email    = sub["email"]
            name     = sub.get("name", "")
            added    = sub.get("added_at", "")[:10]
            selected = "[green]●[/green]" if email in self._selected else " "
            table.add_row(selected, email, name, added)

        sel_count = len(self._selected)
        total     = len(self._all_subs)
        shown     = len(self._filtered)

        self._set_status(
            f"Total: [white]{total}[/white]"
            + (f"  Shown: [yellow]{shown}[/yellow]" if shown != total else "")
            + (f"  Selected: [green]{sel_count}[/green]" if sel_count else ""),
            "dim",
        )

        # Update search bar
        if query:
            self.query_one("#search_bar", Static).update(
                f"[yellow]🔍 Search: '{query}' — {shown} results[/yellow]"
                f"   [dim](S to search again, ESC to clear)[/dim]"
            )
        else:
            self.query_one("#search_bar", Static).update("")

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#sub_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _selected_email(self) -> Optional[str]:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return None
        if table.cursor_row >= len(self._filtered):
            return None
        return self._filtered[table.cursor_row]["email"]

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        """Toggle selection on row tap."""
        email = self._selected_email()
        if not email:
            return
        if email in self._selected:
            self._selected.discard(email)
        else:
            self._selected.add(email)
        self._reload(self._search_query)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_add(self):
        self._open_add_dialog()

    def action_delete_sel(self):
        self._delete_selected()

    def action_search(self):
        self._open_search()

    def action_select_all(self):
        self._selected = {s["email"] for s in self._filtered}
        self._reload(self._search_query)
        self._set_status(
            f"Selected all {len(self._selected)} subscribers", "green"
        )

    def _open_add_dialog(self):
        from ui.input_dialog import InputDialog

        # Step 1: get email
        def on_email(email: str):
            email = email.strip().lower()
            if not email:
                return

            # Step 2: get name
            def on_name(name: str):
                ok = add_subscriber(email=email, name=name.strip())
                if ok:
                    self._reload(self._search_query)
                    self._set_status(
                        f"✓ Added: {email}", "green"
                    )
                else:
                    self._set_status(
                        f"✗ {email} already exists", "red"
                    )

            self.app.push_screen(InputDialog(
                title         = "Subscriber Name",
                label         = f"Enter name for {email} (optional):",
                on_submit     = on_name,
                initial_value = "",
                hint          = "Leave blank if unknown",
            ))

        def validate_email(val: str):
            import re
            val = val.strip().lower()
            if not val:
                return "Email is required"
            pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
            if not re.match(pattern, val):
                return "Invalid email format"

        self.app.push_screen(InputDialog(
            title     = "Add Subscriber",
            label     = "Enter email address:",
            on_submit = on_email,
            hint      = "e.g. jane@example.com",
            validator = validate_email,
        ))

    def _open_search(self):
        from ui.input_dialog import InputDialog

        def on_query(q: str):
            self._selected = set()  # clear selection on new search
            self._reload(q.strip())

        self.app.push_screen(InputDialog(
            title         = "Search Subscribers",
            label         = "Search by email or name:",
            on_submit     = on_query,
            initial_value = self._search_query,
            hint          = "Leave blank to show all",
        ))

    def _delete_selected(self):
        if not self._selected:
            email = self._selected_email()
            if not email:
                self._set_status(
                    "✗ Select subscribers first (tap to select)", "red"
                )
                return
            # Delete just the highlighted row
            self._selected = {email}

        count = remove_subscribers(list(self._selected))
        self._selected = set()
        self._reload(self._search_query)
        self._set_status(
            f"✓ Removed {count} subscriber(s)", "yellow"
        )

    def _import_csv(self):
        from ui.file_browser import FileBrowserScreen

        def on_picked(path: str):
            try:
                imported, skipped = import_from_csv(path)
                self._reload(self._search_query)
                self._set_status(
                    f"✓ Imported {imported} new · {skipped} duplicates skipped",
                    "green",
                )
            except Exception as e:
                self._set_status(f"✗ Import error: {e}", "red")

        self.app.push_screen(FileBrowserScreen(
            on_select  = on_picked,
            filter_ext = [".csv"],
            title      = "Import Subscribers from CSV",
        ))

    def _export_csv(self):
        """Export selected (or all) subscribers to a CSV file."""
        emails = list(self._selected) if self._selected else None
        tmp    = Path.home() / ".voidsend" / (
            "selected_export.csv" if emails else "all_export.csv"
        )
        count = export_to_csv(str(tmp), emails)
        self._set_status(
            f"✓ Exported {count} subscribers → {tmp.name}", "green"
        )

    def _use_selected(self):
        """Pass selected subscribers (or all) to caller as temp CSV."""
        if not self.on_select:
            self.app.pop_screen()
            return

        emails = list(self._selected) if self._selected else None

        if emails:
            csv_path = get_selected_csv(emails)
            count    = len(emails)
        else:
            # No selection — use all visible (filtered or all)
            visible_emails = [s["email"] for s in self._filtered]
            if not visible_emails:
                self._set_status("✗ No subscribers to use", "red")
                return
            csv_path = get_selected_csv(visible_emails)
            count    = len(visible_emails)

        self.on_select(csv_path, count)
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "btn_add":
            self._open_add_dialog()
        elif bid == "btn_search":
            self._open_search()
        elif bid == "btn_select_all":
            self.action_select_all()
        elif bid == "btn_clear_sel":
            self._selected = set()
            self._reload(self._search_query)
        elif bid == "btn_delete":
            self._delete_selected()
        elif bid == "btn_import":
            self._import_csv()
        elif bid == "btn_export":
            self._export_csv()
        elif bid == "btn_use":
            self._use_selected()

    def action_cancel(self):
        self.app.pop_screen()
