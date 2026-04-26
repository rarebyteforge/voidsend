# config/profiles.py
# VoidSend - SMTP Provider Profiles

from dataclasses import dataclass
from typing import Optional

@dataclass
class SMTPProfile:
    name: str
    host: str
    port: int
    use_tls: bool
    use_starttls: bool
    free_tier_note: str
    signup_url: str
    recommended_delay: float
    max_connections: int

PROFILES: dict[str, SMTPProfile] = {
    "brevo": SMTPProfile(
        name="Brevo (formerly Sendinblue)",
        host="smtp-relay.brevo.com",
        port=587,
        use_tls=False,
        use_starttls=True,
        free_tier_note="300 emails/day free",
        signup_url="https://app.brevo.com/account/register",
        recommended_delay=0.5,
        max_connections=3,
    ),
    "mailersend": SMTPProfile(
        name="MailerSend",
        host="smtp.mailersend.net",
        port=587,
        use_tls=False,
        use_starttls=True,
        free_tier_note="3,000 emails/month free",
        signup_url="https://app.mailersend.com/register",
        recommended_delay=0.3,
        max_connections=5,
    ),
    "sendpulse": SMTPProfile(
        name="SendPulse",
        host="smtp-pulse.com",
        port=587,
        use_tls=False,
        use_starttls=True,
        free_tier_note="15,000 emails/month free",
        signup_url="https://login.sendpulse.com/registration/",
        recommended_delay=0.3,
        max_connections=5,
    ),
    "smtp2go": SMTPProfile(
        name="SMTP2GO",
        host="mail.smtp2go.com",
        port=587,
        use_tls=False,
        use_starttls=True,
        free_tier_note="1,000 emails/month free",
        signup_url="https://www.smtp2go.com/signup/",
        recommended_delay=0.5,
        max_connections=3,
    ),
    "mailgun": SMTPProfile(
        name="Mailgun",
        host="smtp.mailgun.org",
        port=587,
        use_tls=False,
        use_starttls=True,
        free_tier_note="5,000 emails/month (3-month trial)",
        signup_url="https://signup.mailgun.com/new/signup",
        recommended_delay=0.2,
        max_connections=8,
    ),
    "sendgrid": SMTPProfile(
        name="SendGrid",
        host="smtp.sendgrid.net",
        port=587,
        use_tls=False,
        use_starttls=True,
        free_tier_note="100 emails/day free forever",
        signup_url="https://signup.sendgrid.com/",
        recommended_delay=0.3,
        max_connections=5,
    ),
    "custom": SMTPProfile(
        name="Custom SMTP Server",
        host="",
        port=587,
        use_tls=False,
        use_starttls=True,
        free_tier_note="Your own SMTP host",
        signup_url="",
        recommended_delay=0.1,
        max_connections=10,
    ),
}

def get_profile(key: str) -> Optional[SMTPProfile]:
    return PROFILES.get(key.lower())

def list_profiles() -> list[tuple[str, SMTPProfile]]:
    return list(PROFILES.items())
