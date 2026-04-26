use anyhow::Result;
use clap::{Parser, Subcommand};

mod config;

use crate::config::{Config, show_profiles};

#[derive(Parser)]
#[command(author, version, about, long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
}

#[derive(Subcommand)]
enum Commands {
    /// Setup or edit SMTP configuration
    Setup,
    /// Test current SMTP configuration
    TestSmtp,
    /// List built-in free/low-cost SMTP profiles
    Profiles,
    /// Send emails (coming soon)
    Send {
        /// Path to CSV file with recipients
        #[arg(short, long)]
        csv: Option<String>,
        /// Path to HTML template file
        #[arg(short, long)]
        template: Option<String>,
    },
}

#[tokio::main]
async fn main() -> Result<()> {
    env_logger::init();

    let cli = Cli::parse();

    match cli.command {
        Some(Commands::Setup) => {
            setup_config().await?;
        }
        Some(Commands::TestSmtp) => {
            test_smtp().await?;
        }
        Some(Commands::Profiles) => {
            show_profiles();
        }
        Some(Commands::Send { csv, template }) => {
            println!("📧 Send command - coming in next update");
            println!("CSV: {:?}, Template: {:?}", csv, template);
        }
        None => {
            println!("VoidSend - Offline Termux Mass Mailer");
            println!("Run `voidsend --help` for available commands");
            println!("\nAvailable commands:");
            println!("  voidsend setup        → Configure your SMTP");
            println!("  voidsend test-smtp    → Test your SMTP config");
            println!("  voidsend profiles     → List free SMTP profiles");
            println!("  voidsend send         → Send emails (coming soon)");
        }
    }

    Ok(())
}

async fn setup_config() -> Result<()> {
    println!("=== VoidSend SMTP Setup ===");

    let mut config = Config::load().unwrap_or_else(|_| Config::default());

    println!("\nEnter your SMTP details:");

    let mut input = String::new();

    println!("Host [{}]: ", config.smtp.host);
    input.clear();
    std::io::stdin().read_line(&mut input)?;
    let host = input.trim();
    if !host.is_empty() {
        config.smtp.host = host.to_string();
    }

    println!("Port [{}]: ", config.smtp.port);
    input.clear();
    std::io::stdin().read_line(&mut input)?;
    if let Ok(port) = input.trim().parse::<u16>() {
        config.smtp.port = port;
    }

    println!("Username: ");
    input.clear();
    std::io::stdin().read_line(&mut input)?;
    config.smtp.username = input.trim().to_string();

    println!("Password: ");
    input.clear();
    std::io::stdin().read_line(&mut input)?;
    config.smtp.password = input.trim().to_string();

    println!("Use TLS/STARTTLS? (y/n) [y]: ");
    input.clear();
    std::io::stdin().read_line(&mut input)?;
    config.smtp.use_tls = input.trim().to_lowercase() != "n";

    config.save()?;

    println!("\n✅ Setup complete! Test it with: voidsend test-smtp");
    Ok(())
}

async fn test_smtp() -> Result<()> {
    let config = Config::load()?;
    config.test_smtp()?;
    Ok(())
}
