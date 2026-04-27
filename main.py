#!/usr/bin/env python3
# main.py
# VoidSend - Privacy-first newsletter tool

import click
from config.settings import load_config, config_exists
from core.mailer import SMTPConfig
from core.notifier import NotificationConfig


def build_smtp_config(cfg: dict) -> SMTPConfig:
    return SMTPConfig(
        host         = cfg["host"],
        port         = cfg["port"],
        username     = cfg["username"],
        password     = cfg["password"],
        use_tls      = cfg.get("use_tls", False),
        use_starttls = cfg.get("use_starttls", True),
        from_name    = cfg.get("from_name", ""),
        from_email   = cfg.get("from_email", ""),
        reply_to     = cfg.get("reply_to"),
    )


def build_notification_config(data: dict) -> NotificationConfig:
    if not data:
        return NotificationConfig()
    return NotificationConfig(**{
        k: v for k, v in data.items()
        if k in NotificationConfig.__dataclass_fields__
    })


@click.command()
@click.option(
    "--passphrase", "-p",
    default=None,
    help="Config decryption passphrase",
)
def main(passphrase):
    """VoidSend — Privacy-first bulk newsletter tool."""

    smtp_config      = None
    notification_cfg = NotificationConfig()
    saved_passphrase = ""

    if config_exists():
        if not passphrase:
            passphrase = click.prompt(
                "Enter config passphrase",
                hide_input=True,
                default="",
                show_default=False,
            )

        cfg_data = load_config(passphrase)

        if cfg_data is None:
            click.echo(
                "✗ Incorrect passphrase or corrupted config. "
                "Starting setup wizard."
            )
        else:
            smtp_config      = build_smtp_config(cfg_data)
            saved_passphrase = passphrase
            click.echo("✓ Config loaded.")

            notif_data = cfg_data.get("notifications")
            if notif_data:
                notification_cfg = build_notification_config(notif_data)

    from ui.app import VoidSendApp
    app = VoidSendApp(
        smtp_config      = smtp_config,
        notification_cfg = notification_cfg,
    )
    # Store passphrase so settings screen can reload saved config
    app._config_passphrase = saved_passphrase
    app.run()


if __name__ == "__main__":
    main()
