# core/mailer.py
# VoidSend - Async SMTP sending engine

import asyncio
import time
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Callable
import aiosmtplib


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    use_tls: bool = False
    use_starttls: bool = True
    from_name: str = ""
    from_email: str = ""
    reply_to: Optional[str] = None


@dataclass
class SendResult:
    email: str
    success: bool
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0


async def send_single(
    smtp_config: SMTPConfig,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> SendResult:
    """Send a single email. Returns SendResult with success/failure info."""
    start = time.monotonic()

    msg = MIMEMultipart("alternative")
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    from_addr = (
        f"{smtp_config.from_name} <{smtp_config.from_email}>"
        if smtp_config.from_name
        else smtp_config.from_email
    )

    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_email
    if smtp_config.reply_to:
        msg["Reply-To"] = smtp_config.reply_to

    try:
        await aiosmtplib.send(
            msg,
            hostname=smtp_config.host,
            port=smtp_config.port,
            username=smtp_config.username,
            password=smtp_config.password,
            use_tls=smtp_config.use_tls,
            start_tls=smtp_config.use_starttls,
            timeout=30,
        )
        duration = (time.monotonic() - start) * 1000
        return SendResult(email=to_email, success=True, duration_ms=duration)

    except aiosmtplib.SMTPException as e:
        duration = (time.monotonic() - start) * 1000
        return SendResult(
            email=to_email,
            success=False,
            error=str(e),
            duration_ms=duration,
        )
    except Exception as e:
        duration = (time.monotonic() - start) * 1000
        return SendResult(
            email=to_email,
            success=False,
            error=f"Unexpected error: {str(e)}",
            duration_ms=duration,
        )


async def send_batch(
    smtp_config: SMTPConfig,
    recipients: list[dict],
    max_connections: int = 5,
    delay_seconds: float = 0.3,
    on_result: Optional[Callable[[SendResult], None]] = None,
    stop_event: Optional[asyncio.Event] = None,
) -> list[SendResult]:
    """Send emails to a batch of recipients with concurrency control."""
    semaphore = asyncio.Semaphore(max_connections)

    async def _send_one(recipient: dict) -> SendResult:
        if stop_event and stop_event.is_set():
            return SendResult(
                email=recipient["email"],
                success=False,
                error="Job cancelled by user",
            )
        async with semaphore:
            result = await send_single(
                smtp_config=smtp_config,
                to_email=recipient["email"],
                subject=recipient["subject"],
                html_body=recipient["html"],
                text_body=recipient.get("text"),
            )
            if on_result:
                on_result(result)
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            return result

    tasks = [asyncio.create_task(_send_one(r)) for r in recipients]
    results = await asyncio.gather(*tasks)
    return list(results)


async def test_connection(smtp_config: SMTPConfig) -> tuple[bool, str]:
    """Test SMTP connection without sending."""
    try:
        async with aiosmtplib.SMTP(
            hostname=smtp_config.host,
            port=smtp_config.port,
            use_tls=smtp_config.use_tls,
            start_tls=smtp_config.use_starttls,
            timeout=15,
        ) as smtp:
            await smtp.login(smtp_config.username, smtp_config.password)
        return True, "Connection successful"
    except aiosmtplib.SMTPAuthenticationError:
        return False, "Authentication failed — check username/password"
    except aiosmtplib.SMTPConnectError as e:
        return False, f"Could not connect to {smtp_config.host}:{smtp_config.port} — {e}"
    except Exception as e:
        return False, f"Connection error: {e}"
