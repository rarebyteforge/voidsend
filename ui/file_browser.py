# ui/file_browser.py
# VoidSend - Reusable file browser screen
# Fixed: Correct Termux home directory detection

from pathlib import Path
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button, Header, Footer,
    DataTable, Static, Input, Label
)
from typing import Optional, Callable
import os


def _get_start_dir() -> Path:
    """
    Detect the best starting directory for the current environment.
    Termux home is /data/data/com.termux/files/home
    """
    # Use HOME env var — most reliable on both Termux and desktop
    home = Path(os.environ.get("HOME", str(Path.home())))

    candidates = [
        home / "voidsend" / "data",   # project data folder first
        home / "voidsend",
        home / "storage" / "shared",  # Termux shared storage if granted
        home,
    ]
    for p in candidates:
        if p.exists():
            return p
    return home


class FileBrowserScreen(Screen):
    """
    Reusable file browser.
    on_select(path: str) called when user confirms a file.
    filter_ext: list of extensions to show e.g. ['.csv', '.html']
    """

    BINDINGS = [
        Binding("escape",    "cancel",  "Cancel"),
        Binding("backspace", "go_up",   "Up"),
        Binding("h",         "go_home", "Home"),
    ]

    CSS = """
    #browser_container {
        height: 1fr;
        padding: 1 2;
    }
    #browser_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 1;
    }
    #current_path {
        color: $accent;
        margin-bottom: 1;
        padding: 0 1;
    }
    #file_table {
        height: 1fr;
        border: solid $accent;
    }
    #manual_path {
        margin-top: 1;
        margin-bottom: 1;
    }
    #btn_row {
        height: auto;
        margin-top: 1;
        padding: 1 0;
    }
    #btn_row Button {
        margin: 0 1;
        min-width: 14;
        height: 3;
    }
    #browser_status {
        min-height: 1;
        margin-top: 1;
    }
    """

    def __init__(
        self,
        on_select: Callable[[str], None],
        start_dir: Optional[str] = None,
        filter_ext: Optional[list[str]] = None,
        title: str = "Select File",
        **kwargs
    ):
        super().__init__(**kwargs)
        self.on_select  = on_select
        self.filter_ext = [e.lower() for e in (filter_ext or [])]
        self.title      = title
        self._entries: list[dict] = []

        if start_dir and Path(start_dir).exists():
            self._cwd = Path(start_dir)
        else:
            self._cwd = _get_start_dir()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"📂  {self.title}", id="browser_title"),
            Static("", id="current_path"),
            DataTable(id="file_table"),
            Label("Type path manually or select above:"),
            Input(
                placeholder="/data/data/com.termux/files/home/...",
                id="manual_path",
            ),
            Static("", id="browser_status"),
            Horizontal(
                Button("↑ Up",     id="btn_up",     variant="default"),
                Button("🏠 Home",  id="btn_home",   variant="default"),
                Button("✓ Select", id="btn_select", variant="success"),
                Button("Cancel",   id="btn_cancel", variant="error"),
                id="btn_row",
            ),
            id="browser_container",
        )
        yield Footer()

    def on_mount(self):
        table = self.query_one(DataTable)
        table.add_columns("", "Name", "Size", "Type")
        self._load_directory(self._cwd)

    def _load_directory(self, path: Path):
        self._cwd = path
        table     = self.query_one(DataTable)
        table.clear()
        self._entries = []

        # Show full real path
        try:
            display_path = str(path.resolve())
        except Exception:
            display_path = str(path)

        self.query_one("#current_path", Static).update(
            f"[bold]📂[/bold] {display_path}"
        )

        try:
            items = sorted(
                path.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            self._set_status("✗ Permission denied", "red")
            return
        except Exception as e:
            self._set_status(f"✗ {e}", "red")
            return

        # Parent directory entry
        if path.parent != path:
            self._entries.append({
                "path":   str(path.parent),
                "name":   "..",
                "is_dir": True,
                "size":   "",
                "type":   "folder",
            })
            table.add_row("📁", "[dim]..[/dim]", "", "↑ up")

        file_count = 0
        dir_count  = 0

        for item in items:
            # Skip hidden files but show them on Termux
            # (many important files start with dot in home)
            is_dir = item.is_dir()

            # Filter by extension
            if not is_dir and self.filter_ext:
                if item.suffix.lower() not in self.filter_ext:
                    continue

            try:
                size = (
                    ""
                    if is_dir
                    else self._format_size(item.stat().st_size)
                )
            except Exception:
                size = ""

            icon  = "📁" if is_dir else self._file_icon(item.suffix)
            ftype = "folder" if is_dir else item.suffix.lstrip(".").upper() or "file"

            self._entries.append({
                "path":   str(item),
                "name":   item.name,
                "is_dir": is_dir,
                "size":   size,
                "type":   ftype,
            })

            name_display = (
                f"[bold]{item.name}[/bold]" if is_dir else item.name
            )
            table.add_row(icon, name_display, size, ftype)

            if is_dir:
                dir_count += 1
            else:
                file_count += 1

        ext_note = (
            f" · showing {', '.join(self.filter_ext)} only"
            if self.filter_ext else ""
        )
        self._set_status(
            f"[dim]{dir_count} folders · {file_count} files{ext_note}[/dim]",
            "white",
        )

    def _format_size(self, size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.0f}{unit}"
            size /= 1024
        return f"{size:.1f}GB"

    def _file_icon(self, ext: str) -> str:
        return {
            ".csv":  "📊",
            ".html": "🌐",
            ".htm":  "🌐",
            ".txt":  "📄",
            ".json": "📋",
            ".pdf":  "📕",
            ".png":  "🖼",
            ".jpg":  "🖼",
            ".jpeg": "🖼",
            ".sh":   "⚙",
            ".py":   "🐍",
        }.get(ext.lower(), "📄")

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#browser_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _selected_entry(self) -> Optional[dict]:
        table = self.query_one(DataTable)
        if table.cursor_row is None:
            return None
        if table.cursor_row >= len(self._entries):
            return None
        return self._entries[table.cursor_row]

    def _open_or_select(self, entry: dict):
        if entry["is_dir"]:
            self._load_directory(Path(entry["path"]))
        else:
            self._confirm_select(entry["path"])

    def _confirm_select(self, path: str):
        p = Path(path)
        if not p.exists():
            self._set_status(f"✗ Not found: {path}", "red")
            return
        if not p.is_file():
            self._set_status("✗ Select a file not a folder", "red")
            return
        if self.filter_ext and p.suffix.lower() not in self.filter_ext:
            self._set_status(
                f"✗ Wrong file type. Need: {', '.join(self.filter_ext)}",
                "red",
            )
            return
        self.on_select(str(p))
        self.app.pop_screen()

    def action_go_up(self):
        parent = self._cwd.parent
        if parent != self._cwd:
            self._load_directory(parent)

    def action_go_home(self):
        self._load_directory(_get_start_dir())

    def on_data_table_row_selected(self, event: DataTable.RowSelected):
        entry = self._selected_entry()
        if entry:
            self._open_or_select(entry)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_up":
            self.action_go_up()
        elif event.button.id == "btn_home":
            self.action_go_home()
        elif event.button.id == "btn_select":
            manual = self.query_one("#manual_path", Input).value.strip()
            if manual:
                self._confirm_select(manual)
            else:
                entry = self._selected_entry()
                if not entry:
                    self._set_status("✗ Select a file first", "red")
                elif entry["is_dir"]:
                    self._load_directory(Path(entry["path"]))
                else:
                    self._confirm_select(entry["path"])
        elif event.button.id == "btn_cancel":
            self.action_cancel()

    def on_input_focus(self, event) -> None:
        try:
            self.query_one("#manual_path", Input).scroll_visible()
        except Exception:
            pass

    def action_cancel(self):
        self.app.pop_screen()
