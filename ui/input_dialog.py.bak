# ui/input_dialog.py
# VoidSend - Full screen input dialog for Termux keyboard reliability
# Pushing a new screen with a single Input reliably triggers the keyboard
# every time, working around Textual's focus issues on Termux.

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.screen import Screen
from textual.widgets import Button, Header, Footer, Input, Label, Static
from typing import Callable, Optional


class InputDialog(Screen):
    """
    Full screen single-field input dialog.
    Reliably triggers Termux keyboard on every open.
    on_submit(value: str) called when user confirms.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    CSS = """
    #dialog_container {
        height: 1fr;
        padding: 2 3;
        align: center middle;
    }
    #dialog_inner {
        height: auto;
        border: solid $accent;
        padding: 2 3;
        width: 100%;
    }
    #dialog_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 2;
    }
    #dialog_label {
        margin-bottom: 1;
        color: $text-muted;
    }
    #dialog_input {
        margin-bottom: 2;
    }
    #dialog_hint {
        color: $text-muted;
        margin-bottom: 2;
        text-style: italic;
    }
    #dialog_status {
        min-height: 1;
        margin-bottom: 1;
    }
    #dialog_btns {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    #dialog_btns Button {
        margin: 0 2;
        min-width: 16;
        height: 3;
    }
    """

    def __init__(
        self,
        title: str,
        label: str,
        on_submit: Callable[[str], None],
        initial_value: str = "",
        hint: str = "",
        password: bool = False,
        validator: Optional[Callable[[str], Optional[str]]] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        self._title         = title
        self._label         = label
        self._on_submit     = on_submit
        self._initial_value = initial_value
        self._hint          = hint
        self._password      = password
        self._validator     = validator

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Vertical(
                Static(self._title, id="dialog_title"),
                Label(self._label, id="dialog_label"),
                Input(
                    value       = self._initial_value,
                    password    = self._password,
                    id          = "dialog_input",
                ),
                Static(
                    f"[dim]{self._hint}[/dim]" if self._hint else "",
                    id="dialog_hint",
                ),
                Static("", id="dialog_status"),
                Container(
                    Button("✓ Confirm", id="btn_confirm", variant="success"),
                    Button("Cancel",    id="btn_cancel",  variant="error"),
                    id="dialog_btns",
                ),
                id="dialog_inner",
            ),
            id="dialog_container",
        )
        yield Footer()

    def on_mount(self):
        # Focus input immediately — triggers keyboard on Termux
        self.call_after_refresh(self._focus_input)

    def _focus_input(self):
        try:
            self.query_one("#dialog_input", Input).focus()
        except Exception:
            pass

    def _set_status(self, msg: str, color: str = "red"):
        self.query_one("#dialog_status", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _submit(self):
        value = self.query_one("#dialog_input", Input).value
        if self._validator:
            error = self._validator(value)
            if error:
                self._set_status(f"✗ {error}", "red")
                return
        self._on_submit(value)
        self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted):
        """Allow Enter key to confirm."""
        self._submit()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_confirm":
            self._submit()
        elif event.button.id == "btn_cancel":
            self.action_cancel()

    def action_cancel(self):
        self.app.pop_screen()
