# ui/setup_screen.py
# VoidSend - First-run SMTP setup wizard

import asyncio
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Button, Label,
    Input, Select, Static, Switch
)
from textual.containers import Container, Vertical, Horizontal
from textual.binding import Binding

from config.profiles import list_profiles, get_profile
from config.settings import save_config
from core.mailer import SMTPConfig, test_connection


class SetupScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, first_run: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.first_run = first_run

    def compose(self) -> ComposeResult:
        profiles = list_profiles()
        options = [(p.name, key) for key, p in profiles]

        yield Header()
        yield Container(
            Static(
                "👋 Welcome to VoidSend — Set up your SMTP provider"
                if self.first_run
                else "⚙  SMTP Configuration",
                id="setup_title",
            ),
            Vertical(
                Label("SMTP Provider"),
                Select(options=options, id="provider_select", value="brevo"),
                Label("", id="provider_note"),
                Label("SMTP Host"),
                Input(placeholder="smtp.example.com", id="smtp_host"),
                Label("SMTP Port"),
                Input(placeholder="587", id="smtp_port", value="587"),
                Horizontal(
                    Vertical(
                        Label("Use TLS"),
                        Switch(id="use_tls", value=False),
                    ),
                    Vertical(
                        Label("Use STARTTLS"),
                        Switch(id="use_starttls", value=True),
                    ),
                    id="tls_row",
                ),
                Label("SMTP Username / API Key"),
                Input(placeholder="your@email.com or API key", id="smtp_user"),
                Label("SMTP Password / Secret"),
                Input(placeholder="password or secret", id="smtp_pass", password=True),
                Label("From Name"),
                Input(placeholder="My Newsletter", id="from_name"),
                Label("From Email"),
                Input(placeholder="hello@yourdomain.com", id="from_email"),
                Label("Reply-To Email (optional)"),
                Input(placeholder="replies@yourdomain.com", id="reply_to"),
                Label("Config Passphrase (encrypts credentials locally)"),
                Input(placeholder="Choose a strong passphrase", id="passphrase", password=True),
                Static("", id="status_msg"),
                Horizontal(
                    Button("Test Connection", id="btn_test", variant="default"),
                    Button("Save & Continue", id="btn_save", variant="success"),
                    Button("Cancel", id="btn_cancel", variant="error"),
                    id="btn_row",
                ),
                id="form_container",
            ),
            id="setup_container",
        )
        yield Footer()

    def on_mount(self):
        self._update_profile_fields("brevo")

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "provider_select":
            self._update_profile_fields(str(event.value))

    def _update_profile_fields(self, key: str):
        profile = get_profile(key)
        if not profile:
            return
        if key != "custom":
            self.query_one("#smtp_host", Input).value = profile.host
            self.query_one("#smtp_port", Input).value = str(profile.port)
            self.query_one("#use_tls", Switch).value = profile.use_tls
            self.query_one("#use_starttls", Switch).value = profile.use_starttls
        note = f"ℹ  {profile.free_tier_note}"
        if profile.signup_url:
            note += f"  |  {profile.signup_url}"
        self.query_one("#provider_note", Label).update(note)

    def _get_form_values(self) -> dict:
        return {
            "provider":    str(self.query_one("#provider_select", Select).value),
            "host":        self.query_one("#smtp_host", Input).value.strip(),
            "port":        int(self.query_one("#smtp_port", Input).value.strip() or "587"),
            "use_tls":     self.query_one("#use_tls", Switch).value,
            "use_starttls":self.query_one("#use_starttls", Switch).value,
            "username":    self.query_one("#smtp_user", Input).value.strip(),
            "password":    self.query_one("#smtp_pass", Input).value,
            "from_name":   self.query_one("#from_name", Input).value.strip(),
            "from_email":  self.query_one("#from_email", Input).value.strip(),
            "reply_to":    self.query_one("#reply_to", Input).value.strip() or None,
        }

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#status_msg", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    async def _run_test(self):
        self._set_status("Testing connection...", "yellow")
        vals = self._get_form_values()
        cfg = SMTPConfig(
            host=vals["host"],
            port=vals["port"],
            username=vals["username"],
            password=vals["password"],
            use_tls=vals["use_tls"],
            use_starttls=vals["use_starttls"],
            from_email=vals["from_email"],
            from_name=vals["from_name"],
        )
        ok, msg = await test_connection(cfg)
        self._set_status(
            f"✓ {msg}" if ok else f"✗ {msg}",
            "green" if ok else "red",
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn_test":
            asyncio.create_task(self._run_test())
        elif event.button.id == "btn_save":
            passphrase = self.query_one("#passphrase", Input).value
            if not passphrase:
                self._set_status("✗ Passphrase is required", "red")
                return
            vals = self._get_form_values()
            if not vals["host"] or not vals["username"] or not vals["password"]:
                self._set_status("✗ Host, username and password are required", "red")
                return
            save_config(vals, passphrase)
            self._set_status("✓ Config saved!", "green")
            self.app.pop_screen()
        elif event.button.id == "btn_cancel":
            self.action_cancel()

    def action_cancel(self):
        if not self.first_run:
            self.app.pop_screen()
