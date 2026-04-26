use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Built-in low-cost / free SMTP profiles for 2026
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SmtpProfile {
    pub name: String,
    pub host: String,
    pub port: u16,
    pub tls: bool,           // true = STARTTLS, false = SSL/TLS
    pub username_example: String,
    pub daily_limit: Option<u32>,
    pub monthly_limit: Option<u32>,
    pub note: String,
}

pub fn get_builtin_profiles() -> HashMap<String, SmtpProfile> {
    let mut profiles = HashMap::new();

    // Brevo (formerly Sendinblue)
    profiles.insert(
        "brevo".to_string(),
        SmtpProfile {
            name: "Brevo".to_string(),
            host: "smtp-relay.brevo.com".to_string(),
            port: 587,
            tls: true,
            username_example: "your-brevo-smtp-key".to_string(),
            daily_limit: Some(300),
            monthly_limit: None,
            note: "Free tier: \\~300 emails/day. Use SMTP key as password.".to_string(),
        },
    );

    // SendPulse
    profiles.insert(
        "sendpulse".to_string(),
        SmtpProfile {
            name: "SendPulse".to_string(),
            host: "smtp-pulse.com".to_string(),
            port: 465,
            tls: false, // SSL
            username_example: "your-email@example.com".to_string(),
            daily_limit: None,
            monthly_limit: Some(12000),
            note: "Free tier: 12,000 emails/month.".to_string(),
        },
    );

    // SMTP2GO
    profiles.insert(
        "smtp2go".to_string(),
        SmtpProfile {
            name: "SMTP2GO".to_string(),
            host: "mail.smtp2go.com".to_string(),
            port: 587,
            tls: true,
            username_example: "your-smtp2go-username".to_string(),
            daily_limit: None,
            monthly_limit: Some(1000),
            note: "Free tier: 1,000 emails/month.".to_string(),
        },
    );

    // MailerSend
    profiles.insert(
        "mailersend".to_string(),
        SmtpProfile {
            name: "MailerSend".to_string(),
            host: "smtp.mailersend.net".to_string(),
            port: 587,
            tls: true,
            username_example: "MS_xxxxxxxx".to_string(),
            daily_limit: None,
            monthly_limit: Some(500),
            note: "Free tier: 500 emails/month.".to_string(),
        },
    );

    profiles
}

pub fn list_profiles() {
    let profiles = get_builtin_profiles();
    println!("VoidSend - Built-in SMTP Profiles (2026 free tiers):\n");
    for (key, p) in profiles {
        println!("• {} ({})", p.name, key);
        println!("  Host : {}:{}", p.host, p.port);
        println!("  TLS  : {}", if p.tls { "STARTTLS" } else { "SSL" });
        println!("  Limit: {} daily / {} monthly", 
            p.daily_limit.map_or("N/A".to_string(), |v| v.to_string()),
            p.monthly_limit.map_or("N/A".to_string(), |v| v.to_string()));
        println!("  Note : {}\n", p.note);
    }
}
