#!/usr/bin/env python3
# main.py
# VoidSend - Privacy-first newsletter tool
# Usage: python main.py [--headless] [--passphrase PASS]

import asyncio
import sys
import click
from config.settings import load_config, config_exists
from core.mailer import SMTPConfig


def build_smtp_config(cfg: dict) -> SMTPConfig:
    return SMTPConfig(
        host=cfg["host"],
        port=cfg["port"],
        username=cfg["username"],
        password=cfg["password"],
        use_tls=cfg.get("use_tls", False),
        use_starttls=cfg.get("use_starttls", True),
        from_name=cfg.get("from_name", ""),
        from_email=cfg.get("from_email", ""),
        reply_to=cfg.get("reply_to"),
    )


@click.command()
@click.option("--passphrase", "-p", default=None, help="Config decryption passphrase")
@click.option("--headless", is_flag=True, help="Run in headless/CLI mode (future use)")
def main(passphrase, headless):
    """VoidSend — Privacy-first bulk newsletter tool."""

    smtp_config = None

    if config_exists():
        if not passphrase:
            passphrase = click.prompt(
                "Enter config passphrase", hide_input=True, default="", show_default=False
            )
        cfg_data = load_config(passphrase)
        if cfg_data is None:
            click.echo("✗ Incorrect passphrase or corrupted config. Starting setup wizard.")
        else:
            smtp_config = build_smtp_config(cfg_data)
            click.echo("✓ Config loaded.")

    if headless:
        click.echo("Headless mode not yet implemented. Launching TUI.")

    # Launch TUI
    from ui.app import VoidSendApp
    app = VoidSendApp(smtp_config=smtp_config)
    app.run()


if __name__ == "__main__":
    main()
