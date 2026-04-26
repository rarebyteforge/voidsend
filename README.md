# VoidSend

**Offline-first bulk SMTP mass mailer built for Termux**

A lightweight, hacker-oriented Rust tool that runs natively on Android (Termux) with **zero server dependency** except the SMTP endpoint you choose.

Default to **your own local SMTP**. Instantly switch to free or low-cost relays. Designed for portability, stealth, and efficiency on mid-range hardware like the Revvl Tab 2.

## Features

- Clean **ratatui** TUI + full headless CLI mode (`voidsend send ...`)
- HTML template support with `{{name}}`, `{{email}}`, `{{custom_field}}` placeholders
- CSV recipient import (email, name + any custom columns)
- Built-in SMTP profiles for 2026 free tiers:
  - Brevo (\~300 emails/day)
  - SendPulse (\~12,000/month)
  - SMTP2GO (\~1,000/month)
  - MailerSend (\~500/month)
- Configurable concurrency and throttling to respect rate limits
- Progress tracking, detailed offline logs (JSON + CSV)
- Secure config storage (TOML)
- Test mode + preview
- Small binary, low resource usage, fully offline after install

## Quick Installation (Termux)

```bash
pkg install rust clang git -y
git clone https://github.com/rarebyteforge/voidsend.git
cd voidsend
cargo build --release --jobs 1
cp target/release/voidsend $PREFIX/bin/
voidsend --help
