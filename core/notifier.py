# core/notifier.py
# VoidSend - Multi-channel notification engine
# Supports: Desktop, Email, Telegram, Discord, Slack

import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass, field
from typing import Optional
import httpx


@dataclass
class NotificationConfig:
    # Global toggle
    enabled: bool = False

    # Milestone notifications (every 25%)
    milestones: bool = False

    # Desktop
    desktop_enabled: bool = False

    # Email
    email_enabled:   bool = False
    email_to:        str  = ""

    # Telegram
    telegram_enabled: bool = False
    telegram_token:   str  = ""
    telegram_chat_id: str  = ""

    # Discord
    discord_enabled:  bool = False
    discord_webhook:  str  = ""

    # Slack
    slack_enabled:    bool = False
    slack_webhook:    str  = ""


@dataclass
class NotificationPayload:
    title:    str
    body:     str
    job_id:   str  = ""
    status:   str  = ""


def _build_message(job_id: str, name: str, status: str,
                   sent: int, failed: int, elapsed: float) -> NotificationPayload:
    title = f"VoidSend — Job {status.capitalize()}"
    body  = (
        f"Job: {name} [{job_id}]\n"
        f"Sent: {sent:,} | Failed: {failed:,}\n"
        f"Duration: {int(elapsed // 60)}m {int(elapsed % 60)}s"
    )
    return NotificationPayload(
        title=title, body=body, job_id=job_id, status=status
    )


# ── Desktop ───────────────────────────────────────────────────────────────────

def _notify_desktop(payload: NotificationPayload):
    try:
        from plyer import notification
        notification.notify(
            title=payload.title,
            message=payload.body,
            app_name="VoidSend",
            timeout=8,
        )
    except Exception:
        pass


# ── Email ─────────────────────────────────────────────────────────────────────

async def _notify_email(
    payload: NotificationPayload,
    cfg: NotificationConfig,
    smtp_config,
):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = payload.title
        msg["From"]    = smtp_config.from_email
        msg["To"]      = cfg.email_to

        html = f"""
        <div style="font-family:monospace;max-width:480px;
        margin:30px auto;background:#1a1a2e;color:#e2e8f0;
        padding:24px;border-radius:6px;border:1px solid #2a2f3d;">
          <div style="color:#00e5a0;font-weight:700;
          font-size:14px;margin-bottom:12px;">{payload.title}</div>
          <pre style="color:#a0aec0;font-size:13px;
          line-height:1.7;margin:0;">{payload.body}</pre>
        </div>
        """
        msg.attach(MIMEText(payload.body, "plain"))
        msg.attach(MIMEText(html, "html"))

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _send_smtp(msg, smtp_config)
        )
    except Exception:
        pass


def _send_smtp(msg, smtp_config):
    import aiosmtplib
    with smtplib.SMTP(smtp_config.host, smtp_config.port) as server:
        if smtp_config.use_starttls:
            server.starttls()
        server.login(smtp_config.username, smtp_config.password)
        server.send_message(msg)


# ── Telegram ──────────────────────────────────────────────────────────────────

async def _notify_telegram(
    payload: NotificationPayload,
    cfg: NotificationConfig,
):
    if not cfg.telegram_token or not cfg.telegram_chat_id:
        return
    try:
        url  = f"https://api.telegram.org/bot{cfg.telegram_token}/sendMessage"
        text = f"*{payload.title}*\n```\n{payload.body}\n```"
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json={
                "chat_id":    cfg.telegram_chat_id,
                "text":       text,
                "parse_mode": "Markdown",
            })
    except Exception:
        pass


# ── Discord ───────────────────────────────────────────────────────────────────

async def _notify_discord(
    payload: NotificationPayload,
    cfg: NotificationConfig,
):
    if not cfg.discord_webhook:
        return
    try:
        color = {
            "completed": 0x00e5a0,
            "failed":    0xff6b6b,
            "cancelled": 0xf5a623,
        }.get(payload.status.lower(), 0x0099ff)

        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(cfg.discord_webhook, json={
                "embeds": [{
                    "title":       payload.title,
                    "description": f"```\n{payload.body}\n```",
                    "color":       color,
                }]
            })
    except Exception:
        pass


# ── Slack ─────────────────────────────────────────────────────────────────────

async def _notify_slack(
    payload: NotificationPayload,
    cfg: NotificationConfig,
):
    if not cfg.slack_webhook:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(cfg.slack_webhook, json={
                "text": f"*{payload.title}*\n```{payload.body}```"
            })
    except Exception:
        pass


# ── Main dispatcher ───────────────────────────────────────────────────────────

async def notify_job_event(
    cfg: NotificationConfig,
    smtp_config,
    job_id:  str,
    name:    str,
    status:  str,
    sent:    int,
    failed:  int,
    elapsed: float,
):
    """
    Fire notifications to all enabled channels.
    Called on job completion, failure, or cancellation.
    """
    if not cfg.enabled:
        return

    payload = _build_message(job_id, name, status, sent, failed, elapsed)
    tasks   = []

    if cfg.desktop_enabled:
        _notify_desktop(payload)

    if cfg.email_enabled and cfg.email_to and smtp_config:
        tasks.append(_notify_email(payload, cfg, smtp_config))

    if cfg.telegram_enabled:
        tasks.append(_notify_telegram(payload, cfg))

    if cfg.discord_enabled:
        tasks.append(_notify_discord(payload, cfg))

    if cfg.slack_enabled:
        tasks.append(_notify_slack(payload, cfg))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_channel(
    channel:     str,
    cfg:         NotificationConfig,
    smtp_config  = None,
) -> tuple[bool, str]:
    """
    Test a single notification channel.
    Returns (success, message).
    """
    payload = NotificationPayload(
        title="VoidSend — Test Notification",
        body="This is a test from VoidSend.\nNotifications are working correctly.",
        job_id="TEST",
        status="test",
    )

    try:
        if channel == "desktop":
            _notify_desktop(payload)
            return True, "Desktop notification sent"

        elif channel == "email":
            if not cfg.email_to:
                return False, "No email address configured"
            if not smtp_config:
                return False, "No SMTP config loaded"
            await _notify_email(payload, cfg, smtp_config)
            return True, f"Test email sent to {cfg.email_to}"

        elif channel == "telegram":
            if not cfg.telegram_token or not cfg.telegram_chat_id:
                return False, "Token and Chat ID are required"
            await _notify_telegram(payload, cfg)
            return True, "Telegram message sent"

        elif channel == "discord":
            if not cfg.discord_webhook:
                return False, "Webhook URL is required"
            await _notify_discord(payload, cfg)
            return True, "Discord message sent"

        elif channel == "slack":
            if not cfg.slack_webhook:
                return False, "Webhook URL is required"
            await _notify_slack(payload, cfg)
            return True, "Slack message sent"

        else:
            return False, f"Unknown channel: {channel}"

    except Exception as e:
        return False, str(e)
