# ui/notifications_screen.py
# VoidSend - Notification settings screen

import asyncio
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.screen import Screen
from textual.widgets import (
    Button, Header, Footer, Input,
    Label, Static, Switch
)
from core.notifier import NotificationConfig, test_channel


class NotificationsScreen(Screen):

    BINDINGS = [Binding("escape", "cancel", "Back")]

    def __init__(self, cfg: NotificationConfig, smtp_config=None, **kwargs):
        super().__init__(**kwargs)
        self.cfg         = cfg
        self.smtp_config = smtp_config

    def compose(self) -> ComposeResult:
        c = self.cfg
        yield Header()
        yield Container(
            Static("🔔  Notification Settings", id="notif_title"),
            ScrollableContainer(

                # ── Global ────────────────────────────────────────────────
                Static("── Global ──────────────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Enable Notifications"),
                        Switch(id="enabled", value=c.enabled),
                    ),
                    Vertical(
                        Label("Milestone Alerts (every 25%)"),
                        Switch(id="milestones", value=c.milestones),
                    ),
                    id="global_row",
                ),

                # ── Desktop ───────────────────────────────────────────────
                Static("── Desktop ─────────────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Enable Desktop Notifications"),
                        Switch(id="desktop_enabled", value=c.desktop_enabled),
                    ),
                    Vertical(
                        Label(""),
                        Button(
                            "Test Desktop",
                            id="btn_test_desktop",
                            variant="default",
                        ),
                    ),
                    id="desktop_row",
                ),

                # ── Email ─────────────────────────────────────────────────
                Static("── Email ───────────────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Enable Email Notifications"),
                        Switch(id="email_enabled", value=c.email_enabled),
                    ),
                    Vertical(
                        Label("Send Notifications To"),
                        Input(
                            placeholder="your@email.com",
                            id="email_to",
                            value=c.email_to,
                        ),
                    ),
                    Vertical(
                        Label(""),
                        Button(
                            "Test Email",
                            id="btn_test_email",
                            variant="default",
                        ),
                    ),
                    id="email_row",
                ),

                # ── Telegram ──────────────────────────────────────────────
                Static("── Telegram ────────────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Enable Telegram"),
                        Switch(id="telegram_enabled", value=c.telegram_enabled),
                    ),
                    Vertical(
                        Label("Bot Token"),
                        Input(
                            placeholder="123456:ABCdef...",
                            id="telegram_token",
                            value=c.telegram_token,
                            password=True,
                        ),
                    ),
                    Vertical(
                        Label("Chat ID"),
                        Input(
                            placeholder="-100123456789",
                            id="telegram_chat_id",
                            value=c.telegram_chat_id,
                        ),
                    ),
                    id="telegram_row",
                ),
                Horizontal(
                    Static(
                        "[dim]Get token from @BotFather — "
                        "get Chat ID from @userinfobot[/dim]",
                        id="telegram_help",
                    ),
                    Button(
                        "Test Telegram",
                        id="btn_test_telegram",
                        variant="default",
                    ),
                    id="telegram_actions",
                ),

                # ── Discord ───────────────────────────────────────────────
                Static("── Discord ─────────────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Enable Discord"),
                        Switch(id="discord_enabled", value=c.discord_enabled),
                    ),
                    Vertical(
                        Label("Webhook URL"),
                        Input(
                            placeholder="https://discord.com/api/webhooks/...",
                            id="discord_webhook",
                            value=c.discord_webhook,
                            password=True,
                        ),
                    ),
                    Vertical(
                        Label(""),
                        Button(
                            "Test Discord",
                            id="btn_test_discord",
                            variant="default",
                        ),
                    ),
                    id="discord_row",
                ),

                # ── Slack ─────────────────────────────────────────────────
                Static("── Slack ───────────────────────────────────", classes="section_sep"),
                Horizontal(
                    Vertical(
                        Label("Enable Slack"),
                        Switch(id="slack_enabled", value=c.slack_enabled),
                    ),
                    Vertical(
                        Label("Webhook URL"),
                        Input(
                            placeholder="https://hooks.slack.com/services/...",
                            id="slack_webhook",
                            value=c.slack_webhook,
                            password=True,
                        ),
                    ),
                    Vertical(
                        Label(""),
                        Button(
                            "Test Slack",
                            id="btn_test_slack",
                            variant="default",
                        ),
                    ),
                    id="slack_row",
                ),

                Static("", id="status_msg"),
                id="notif_scroll",
            ),
            Horizontal(
                Button("Save",         id="btn_save",   variant="success"),
                Button("Back [ESC]",   id="btn_back",   variant="default"),
                id="notif_actions",
            ),
            id="notif_container",
        )
        yield Footer()

    def _set_status(self, msg: str, color: str = "white"):
        self.query_one("#status_msg", Static).update(
            f"[{color}]{msg}[/{color}]"
        )

    def _collect_cfg(self) -> NotificationConfig:
        def sw(id_: str) -> bool:
            try:
                return self.query_one(f"#{id_}", Switch).value
            except Exception:
                return False

        def inp(id_: str) -> str:
            try:
                return self.query_one(f"#{id_}", Input).value.strip()
            except Exception:
                return ""

        return NotificationConfig(
            enabled           = sw("enabled"),
            milestones        = sw("milestones"),
            desktop_enabled   = sw("desktop_enabled"),
            email_enabled     = sw("email_enabled"),
            email_to          = inp("email_to"),
            telegram_enabled  = sw("telegram_enabled"),
            telegram_token    = inp("telegram_token"),
            telegram_chat_id  = inp("telegram_chat_id"),
            discord_enabled   = sw("discord_enabled"),
            discord_webhook   = inp("discord_webhook"),
            slack_enabled     = sw("slack_enabled"),
            slack_webhook     = inp("slack_webhook"),
        )

    async def _run_test(self, channel: str):
        self._set_status(f"Testing {channel}...", "yellow")
        cfg = self._collect_cfg()
        ok, msg = await test_channel(channel, cfg, self.smtp_config)
        self._set_status(
            f"✓ {msg}" if ok else f"✗ {msg}",
            "green" if ok else "red",
        )

    def _save(self):
        self.cfg = self._collect_cfg()
        # Persist to app for use across sessions
        if hasattr(self.app, "notification_cfg"):
            self.app.notification_cfg = self.cfg
        self._set_status("✓ Notification settings saved", "green")

    def on_button_pressed(self, event: Button.Pressed):
        bid = event.button.id
        if bid == "btn_test_desktop":
            asyncio.create_task(self._run_test("desktop"))
        elif bid == "btn_test_email":
            asyncio.create_task(self._run_test("email"))
        elif bid == "btn_test_telegram":
            asyncio.create_task(self._run_test("telegram"))
        elif bid == "btn_test_discord":
            asyncio.create_task(self._run_test("discord"))
        elif bid == "btn_test_slack":
            asyncio.create_task(self._run_test("slack"))
        elif bid == "btn_save":
            self._save()
        elif bid == "btn_back":
            self.action_cancel()

    def action_cancel(self):
        self._save()
        self.app.pop_screen()
