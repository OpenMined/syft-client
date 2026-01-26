"""Unified initialization flow for all background services."""

from pathlib import Path

import click
import yaml


def get_creds_dir() -> Path:
    """Get the credentials directory."""
    colab_drive = Path("/content/drive/MyDrive")
    if colab_drive.exists():
        return colab_drive / "syft-creds"
    return Path.home() / ".syft-creds"


def run_init_flow():
    """Run unified setup for all background services."""
    click.echo()
    click.echo("🔧 SYFTBOX BACKGROUND SERVICES SETUP")
    click.echo("=" * 50)
    click.echo()
    click.echo("This will configure both notification and auto-approval services.")
    click.echo()

    creds_dir = get_creds_dir()
    config_path = creds_dir / "config.yaml"

    # Load existing config if present
    existing_config = {}
    if config_path.exists():
        with open(config_path) as f:
            existing_config = yaml.safe_load(f) or {}
        click.echo(f"Found existing config at {config_path}")
        if not click.confirm("Update existing configuration?", default=True):
            click.echo("Setup cancelled.")
            return

    click.echo()
    click.echo("━" * 50)
    click.echo("COMMON SETTINGS")
    click.echo("━" * 50)
    click.echo()

    # Common settings
    default_email = existing_config.get("do_email", "")
    do_email = click.prompt("Data Owner email address", default=default_email or None)

    default_syftbox = existing_config.get(
        "syftbox_root", str(Path.home() / f"SyftBox_{do_email}")
    )
    syftbox_root = click.prompt("SyftBox root directory", default=default_syftbox)

    # Gmail setup for notifications
    click.echo()
    click.echo("━" * 50)
    click.echo("GMAIL AUTHENTICATION")
    click.echo("━" * 50)
    click.echo()

    gmail_token_path = creds_dir / "gmail_token.json"
    credentials_path = creds_dir / "credentials.json"

    if gmail_token_path.exists():
        click.echo(f"✅ Gmail token exists: {gmail_token_path}")
    else:
        click.echo("Gmail is required for email notifications.")
        click.echo()

        if not credentials_path.exists():
            click.echo(f"❌ credentials.json not found at {credentials_path}")
            click.echo()
            click.echo("To get credentials.json:")
            click.echo(
                "  1. Go to Google Cloud Console → APIs & Services → Credentials"
            )
            click.echo("  2. Create OAuth 2.0 Client ID (Desktop app)")
            click.echo("  3. Download as credentials.json")
            click.echo(f"  4. Place it at: {credentials_path}")
            click.echo()
            creds_input = click.prompt(
                "Or enter path to credentials.json", type=click.Path(exists=True)
            )
            credentials_path = Path(creds_input).expanduser()

        click.echo("📧 Setting up Gmail authentication...")
        try:
            from syft_notify.gmail import GmailAuth

            auth = GmailAuth()
            credentials = auth.setup_auth(credentials_path)
            gmail_token_path.parent.mkdir(parents=True, exist_ok=True)
            gmail_token_path.write_text(credentials.to_json())
            click.echo(f"✅ Gmail token saved: {gmail_token_path}")
        except ImportError:
            click.echo("⚠️  syft-notify not installed, skipping Gmail setup", err=True)
        except Exception as e:
            click.echo(f"⚠️  Gmail setup failed: {e}", err=True)

    # Notification settings
    click.echo()
    click.echo("━" * 50)
    click.echo("NOTIFICATION SERVICE (syft-notify)")
    click.echo("━" * 50)
    click.echo()

    existing_notify = existing_config.get("notify", {})

    notify_jobs = click.confirm(
        "Enable email notifications for new jobs?",
        default=existing_notify.get("monitor_jobs", True),
    )
    notify_peers = click.confirm(
        "Enable email notifications for peer requests?",
        default=existing_notify.get("monitor_peers", True),
    )
    notify_interval = click.prompt(
        "Check interval (seconds)",
        type=int,
        default=existing_notify.get("interval", 30),
    )

    # Auto-approval settings
    click.echo()
    click.echo("━" * 50)
    click.echo("AUTO-APPROVAL SERVICE (syft-approve)")
    click.echo("━" * 50)
    click.echo()

    existing_approve = existing_config.get("approve", {})
    existing_jobs = existing_approve.get("jobs", {})
    existing_peers = existing_approve.get("peers", {})

    click.echo("📋 Job Auto-Approval:")
    approve_jobs = click.confirm(
        "  Enable automatic job approval?",
        default=existing_jobs.get("enabled", True),
    )
    jobs_peers_only = False
    if approve_jobs:
        jobs_peers_only = click.confirm(
            "  Only approve jobs from approved peers?",
            default=existing_jobs.get("peers_only", True),
        )

    click.echo()
    click.echo("🤝 Peer Auto-Approval:")
    approve_peers = click.confirm(
        "  Enable automatic peer approval?",
        default=existing_peers.get("enabled", False),
    )
    approved_domains = []
    if approve_peers:
        default_domains = ",".join(
            existing_peers.get("approved_domains", ["openmined.org"])
        )
        domains_input = click.prompt(
            "  Approved domains (comma-separated)", default=default_domains
        )
        approved_domains = [d.strip() for d in domains_input.split(",") if d.strip()]

    approve_interval = click.prompt(
        "Check interval (seconds)",
        type=int,
        default=existing_approve.get("interval", 5),
    )

    # Build config
    config = {
        "do_email": do_email,
        "syftbox_root": syftbox_root,
        "notify": {
            "interval": notify_interval,
            "monitor_jobs": notify_jobs,
            "monitor_peers": notify_peers,
        },
        "approve": {
            "interval": approve_interval,
            "jobs": {
                "enabled": approve_jobs,
                "peers_only": jobs_peers_only,
                "required_scripts": existing_jobs.get("required_scripts", {}),
                "required_filenames": existing_jobs.get("required_filenames", []),
                "required_json_keys": existing_jobs.get("required_json_keys", {}),
                "allowed_users": existing_jobs.get("allowed_users", []),
            },
            "peers": {
                "enabled": approve_peers,
                "approved_domains": approved_domains,
                "auto_share_datasets": existing_peers.get("auto_share_datasets", []),
            },
        },
    }

    # Save config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    click.echo()
    click.echo("━" * 50)
    click.echo("SETUP COMPLETE")
    click.echo("━" * 50)
    click.echo()
    click.echo(f"✅ Config saved: {config_path}")
    click.echo()
    click.echo("Available commands:")
    click.echo("  syft-bg status     - Show service status")
    click.echo("  syft-bg start      - Start all services")
    click.echo("  syft-bg stop       - Stop all services")
    click.echo("  syft-bg logs <svc> - View service logs")
    click.echo()
    click.echo("To edit advanced settings (required_scripts, allowed_users, etc.):")
    click.echo(f"  {config_path}")
    click.echo()
