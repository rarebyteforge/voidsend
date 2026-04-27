# ui/setup_screen.py
# VoidSend - SMTP setup wizard
# Fixed: load saved config into fields on mount so settings persist

import asyncio
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Button,
    Label, Static, Select
)
from textual.containers import Container, Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding

from config.profiles import list_profiles, get_profile
from config.settings import save_config, load_config, config_exists
from core.mailer import SMTPConfig, test_connection
from core.notifier import NotificationConfig


TLS_OPTIONS = [
    ("STARTTLS (recommended — port 587)", "starttls"),
    ("SSL/TLS (port 465)",                "tls"),
    ("None (not recommended)",            "none"),
]


class SetupScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    CSS = """
    #setup_container {
        height: 1fr;
        padding: 1 2;
    }
    #setup_title {
        background: $accent;
        color: $text;
        text-align: center;
        padding: 1;
        text-style: bold;
        margin-bottom: 1;
    }
    #form_scroll {
        height: 1fr;
        border: solid $accent;
        padding: 1 2;
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
    Label {
        margin-top: 1;
    }
    Select {
        margin-bottom: 1;
    }
    #status_msg {
        margin-top: 1;
        min-height: 1;
    }
    #provider_note {
        margin-bottom: 1;
        color: $text-muted;
    }
    """

    def __init__(self, first_run: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.first_run   = first_run
        self._host       = ""
        self._port       = "587"
        self._username   = ""
        self._password   = ""
        self._from_name  = ""
        self._from_email = ""
        self._reply_to   = ""
        self._passphrase = ""
        self._tls_mode   = "starttls"

    def compose(self) -> ComposeResult:
        profiles = list_profiles()
        options  = [(p.name, key) for key, p in profiles]

        yield Header()
        yield Container(
            Static(
                "👋 Welcome — Set up your SMTP provider"
                if self.first_run else "⚙  SMTP Configuration",
                id="setup_title",
            ),
            ScrollableContainer(
                Label("SMTP Provider"),
                Select(
                    options=options,
                    id="provider_select",
                    value="brevo",
                ),
                Label("", id="provider_note"),
                Label("SMTP Host"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_host"),
                    Button("edit", id="btn_edit_host", variant="default"),
                    classes="field_row",
                ),
                Label("SMTP Port"),
                Horizontal(
                    Static("587", id="val_port"),
                    Button("edit", id="btn_edit_port", variant="default"),
                    classes="field_row",
                ),
                Label("TLS Mode"),
                Select(
                    options=TLS_OPTIONS,
                    id="tls_mode",
                    value="starttls",
                ),
                Label("SMTP Username / API Key"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_username"),
                    Button("edit", id="btn_edit_username", variant="default"),
                    classes="field_row",
                ),
                Label("SMTP Password / Secret"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_password"),
                    Button("edit", id="btn_edit_password", variant="default"),
                    classes="field_row",
                ),
                Label("From Name"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_from_name"),
                    Button("edit", id="btn_edit_from_name", variant="default"),
                    classes="field_row",
                ),
                Label("From Email"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_from_email"),
                    Button("edit", id="btn_edit_from_email", variant="default"),
                    classes="field_row",
                ),
                Label("Reply-To Email (optional)"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_reply_to"),
                    Button("edit", id="btn_edit_reply_to", variant="default"),
                    classes="field_row",
                ),
                Label("Config Passphrase (encrypts credentials locally)"),
                Horizontal(
                    Static("[dim]not set[/dim]", id="val_passphrase"),
                    Button("edit", id="btn_edit_passphrase", variant="default"),
                    classes="field_row",
                ),
                Static("", id="status_msg"),
                id="form_scroll",
            ),
            Horizontal(
                Button("Test",    id="btn_test",          variant="default"),
                Button("Notify",  id="btn_notifications", variant="default"),
                Button("Save",    id="btn_save",          variant="success"),
                Button("Cancel",  id="btn_cancel",        variant="error"),
                id="action_bar",
            ),
            id="setup_container",
        )
        yield Footer()

    def on_mount(self):
        self.call_after_refresh(self._load_and_init)

    def _load_and_init(self):
        """Load saved config into fields if available."""
        # Try to get passphrase from app context first
        saved_passphrase = getattr(self.app, "_config_passphrase", "")

        if saved_passphrase and config_exists():
            cfg = load_config(saved_passphrase)
            if cfg:
                self._host        = cfg.get("host", "")
                self._port        = str(cfg.get("port", "587"))
                self._username    = cfg.get("username", "")
                self._password    = cfg.get("password", "")
                self._from_name   = cfg.get("from_name", "")
                self._from_email  = cfg.get("from_email", "")
                self._reply_to    = cfg.get("reply_to", "") or ""
                self._passphrase  = saved_passphrase

                # Set TLS mode from saved values
                if cfg.get("use_tls"):
                    self._tls_mode = "tls"
                elif cfg.get("use_starttls"):
                    self._tls_mode = "starttls"
                else:
                    self._tls_mode = "none"

                self._refresh_all_fields()
                self._set_status("✓ Config loaded", "green")
                return

        # No saved config — apply provider defaults
        self._update_profile_fields("brevo")

        try:
            self.query_one(
                "#form_scroll", ScrollableContainer
            ).scroll_home(animate=False)
        except Exception:
            pass

    def _refresh_all_fields(self):
        """Push all instance vars into display widgets."""
        self._set_field("val_host",       self._host)
        self._set_field("val_port",       self._port)
        self._set_field("val_username",   self._username)
        self._set_field("val_password",   self._password,   mask=True)
        self._set_field("val_from_name",  self._from_name)
        self._set_field("val_from_email", self._from_email)
        self._set_field("val_reply_to",   self._reply_to)
        self._set_field("val_passphrase", self._passphrase, mask=True)

        try:
            self.query_one("#tls_mode", Select).value = self._tls_mode
        except Exception:
            pass

        try:
            self.query_one(
                "#form_scroll", ScrollableContainer
            ).scroll_home(animate=False)
        except Exception:
            pass

    def on_select_changed(self, event: Select.Changed):
        if event.select.id == "provider_select":
            self._update_profile_fields(str(event.value))
        elif event.select.id == "tls_mode":
            self._tls_mode = str(event.value)

    def _update_profile_fields(self, key: str):
        profile = get_profile(key)
        if not profile:
            return
        if key != "custom":
            self._host = profile.host
            self._port = str(profile.port)
            if profile.use_tls:
                self._tls_mode = "tls"
            elif profile.use_starttls:
                self._tls_mode = "starttls"
            else:
                self._tls_mode = "none"
            self._set_field("val_host", self._host)
            self._set_field("val_port", self._port)
            try:
                self.query_one("#tls_mode", Select).value = self._tls_mode
            except Exception:
                pass

        note = f"ℹ  {profile.free_tier_note}"
        if profile.signup_url:
            note += f"  |  {profile.signup_url}"
        try:
            self.query_one("#provider_note", Label).update(note)
        except Exception:
            pass

    def _set_field(self, widget_id: str, value: str, mask: bool = False):
        try:
            w = self.query_one(f"#{widget_id}", Static)
            if value:
                display = ("•" * min(len(value), 12)) if mask else value
                w.update(display)
            else:
                w.update("[dim]not set[/dim]")
        except Exception:
            pass

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#status_msg", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _edit_field(
        self,
        title: str,
        label: str,
        attr: str,
        widget_id: str,
        hint: str = "",
        password: bool = False,
        validator=None,
    ):
        from ui.input_dialog import InputDialog
        def on_submit(val: str):
            setattr(self, attr, val)
            self._set_field(widget_id, val, mask=password)
        self.app.push_screen(InputDialog(
            title         = title,
            label         = label,
            on_submit     = on_submit,
            initial_value = getattr(self, attr, ""),
            hint          = hint,
            password      = password,
            validator     = validator,
        ))

    def _get_tls_flags(self) -> tuple[bool, bool]:
        if self._tls_mode == "tls":
            return True, False
        elif self._tls_mode == "starttls":
            return False, True
        return False, False

    def _build_smtp_config(self) -> SMTPConfig:
        use_tls, use_starttls = self._get_tls_flags()
        return SMTPConfig(
            host         = self._host,
            port         = int(self._port or "587"),
            username     = self._username,
            password     = self._password,
            use_tls      = use_tls,
            use_starttls = use_starttls,
            from_email   = self._from_email,
            from_name    = self._from_name,
        )

    async def _run_test(self):
        self._set_status("Testing connection...", "yellow")
        if not self._host or not self._username or not self._password:
            self._set_status(
                "✗ Host, username and password required to test", "red"
            )
            return
        cfg     = self._build_smtp_config()
        ok, msg = await test_connection(cfg)
        self._set_status(
            f"✓ {msg}" if ok else f"✗ {msg}",
            "green" if ok else "red",
        )

    def _open_notifications(self):
        from ui.notifications_screen import NotificationsScreen
        smtp_config = None
        try:
            if self._host and self._username:
                smtp_config = self._build_smtp_config()
        except Exception:
            pass
        notif_cfg = getattr(
            self.app, "notification_cfg", NotificationConfig()
        )
        self.app.push_screen(
            NotificationsScreen(cfg=notif_cfg, smtp_config=smtp_config)
        )

    def _save_and_continue(self):
        if not self._passphrase:
            self._set_status("✗ Passphrase required — tap edit", "red")
            return
        if not self._host or not self._username or not self._password:
            self._set_status(
                "✗ Host, username and password required", "red"
            )
            return
        if not self._from_email:
            self._set_status("✗ From Email required", "red")
            return

        use_tls, use_starttls = self._get_tls_flags()
        vals = {
            "provider":     str(
                self.query_one("#provider_select", Select).value
            ),
            "host":         self._host,
            "port":         int(self._port or "587"),
            "use_tls":      use_tls,
            "use_starttls": use_starttls,
            "username":     self._username,
            "password":     self._password,
            "from_name":    self._from_name,
            "from_email":   self._from_email,
            "reply_to":     self._reply_to or None,
        }

        save_config(vals, self._passphrase)

        # Store passphrase in app so settings screen can reload it next time
        self.app._config_passphrase = self._passphrase
        self.app.smtp_config        = self._build_smtp_config()

        self._set_status("✓ Config saved!", "green")

        from ui.app import JobDashboard
        if self.first_run:
            self.app.pop_screen()
            self.app.push_screen(
                JobDashboard(
                    job_manager = self.app.job_manager,
                    smtp_config = self.app.smtp_config,
                )
            )
        else:
            self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "btn_edit_host":
            self._edit_field(
                "SMTP Host", "Enter SMTP host:",
                "_host", "val_host",
                hint="e.g. smtp-relay.brevo.com",
            )
        elif bid == "btn_edit_port":
            self._edit_field(
                "SMTP Port", "Enter SMTP port number:",
                "_port", "val_port",
                hint="587 for STARTTLS · 465 for SSL",
            )
        elif bid == "btn_edit_username":
            self._edit_field(
                "SMTP Username", "Enter username or API key:",
                "_username", "val_username",
                hint="Your Brevo account email or API key",
            )
        elif bid == "btn_edit_password":
            self._edit_field(
                "SMTP Password", "Enter password or secret:",
                "_password", "val_password",
                password=True,
                hint="Your SMTP password or API secret",
            )
        elif bid == "btn_edit_from_name":
            self._edit_field(
                "From Name", "Enter sender display name:",
                "_from_name", "val_from_name",
                hint="e.g. My Newsletter",
            )
        elif bid == "btn_edit_from_email":
            self._edit_field(
                "From Email", "Enter sender email address:",
                "_from_email", "val_from_email",
                hint="Must be verified in your SMTP provider",
            )
        elif bid == "btn_edit_reply_to":
            self._edit_field(
                "Reply-To", "Enter reply-to address (optional):",
                "_reply_to", "val_reply_to",
                hint="Leave blank to use From Email",
            )
        elif bid == "btn_edit_passphrase":
            self._edit_field(
                "Config Passphrase",
                "Enter passphrase to encrypt your credentials:",
                "_passphrase", "val_passphrase",
                password=True,
                hint="You need this each time you launch VoidSend",
            )
        elif bid == "btn_test":
            asyncio.create_task(self._run_test())
        elif bid == "btn_notifications":
            self._open_notifications()
        elif bid == "btn_save":
            self._save_and_continue()
        elif bid == "btn_cancel":
            self.action_cancel()

    def action_cancel(self):
        if not self.first_run:
            self.app.pop_screen()
