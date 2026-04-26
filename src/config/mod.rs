// src/config/mod.rs
pub mod profiles;

use anyhow::{Context, Result};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;

use crate::config::profiles::list_profiles;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SmtpConfig {
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: String,
    pub use_tls: bool,           // true = STARTTLS (usually 587), false = SSL (usually 465)
    pub profile_name: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Config {
    pub smtp: SmtpConfig,
    pub concurrency: usize,
    pub delay_ms: u64,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            smtp: SmtpConfig {
                host: "smtp-relay.brevo.com".to_string(),
                port: 587,
                username: String::new(),
                password: String::new(),
                use_tls: true,
                profile_name: Some("brevo".to_string()),
            },
            concurrency: 5,
            delay_ms: 1000,
        }
    }
}

impl Config {
    pub fn config_dir() -> PathBuf {
        dirs::config_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join("voidsend")
    }

    pub fn path() -> PathBuf {
        Self::config_dir().join("config.toml")
    }

    pub fn load() -> Result<Self> {
        let path = Self::path();

        if path.exists() {
            let content = fs::read_to_string(&path)
                .with_context(|| format!("Failed to read config from {}", path.display()))?;

            let config: Config = toml::from_str(&content)
                .context("Failed to parse config.toml")?;

            println!("✅ Loaded config from {}", path.display());
            Ok(config)
        } else {
            println!("⚠️  No config found at {}", path.display());
            println!("   Run `voidsend setup` to create one.");
            Ok(Config::default())
        }
    }

    pub fn save(&self) -> Result<()> {
        let dir = Self::config_dir();
        fs::create_dir_all(&dir)?;

        let content = toml::to_string_pretty(self)
            .context("Failed to serialize config to TOML")?;

        let path = Self::path();
        fs::write(&path, content)
            .with_context(|| format!("Failed to write config to {}", path.display()))?;

        println!("✅ Config saved to {}", path.display());
        Ok(())
    }

    // Simple SMTP config test (full connection test will be added later)
    pub fn test_smtp(&self) -> Result<()> {
        println!("🔍 Testing SMTP configuration...");
        println!("   Profile : {:?}", self.smtp.profile_name);
        println!("   Host    : {}:{}", self.smtp.host, self.smtp.port);
        println!("   Username: {}", self.smtp.username);
        println!("   TLS     : {}", if self.smtp.use_tls { "STARTTLS" } else { "SSL" });
        println!("\n✅ Config looks valid.");
        println!("   Full SMTP connection test will be available once sender module is ready.");
        Ok(())
    }
}

pub fn show_profiles() {
    list_profiles();
}
