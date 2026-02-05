"""Main initialization flow for syft-bg services."""

from pathlib import Path

import click
import yaml

from syft_bg.cli.init.drive_setup import setup_drive
from syft_bg.cli.init.gmail_setup import setup_gmail
from syft_bg.common.config import get_creds_dir
from syft_bg.common.drive import is_colab


def run_init_flow(
    cli_filenames: list[str] | None = None,
    cli_allowed_users: list[str] | None = None,
):
    """Run unified setup for all background services.

    Args:
        cli_filenames: Required filenames from CLI (None = prompt user)
        cli_allowed_users: Allowed users from CLI (None = prompt user)
    """
    click.echo()
    click.echo("SYFTBOX BACKGROUND SERVICES SETUP")
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

    # Common settings
    click.echo()
    click.echo("-" * 50)
    click.echo("COMMON SETTINGS")
    click.echo("-" * 50)
    click.echo()

    default_email = existing_config.get("do_email", "")
    do_email = click.prompt("Data Owner email address", default=default_email or None)

    default_syftbox = existing_config.get(
        "syftbox_root", str(Path.home() / f"SyftBox_{do_email}")
    )
    syftbox_root = click.prompt("SyftBox root directory", default=default_syftbox)

    # Gmail setup
    click.echo()
    click.echo("-" * 50)
    click.echo("GMAIL AUTHENTICATION")
    click.echo("-" * 50)
    click.echo()

    gmail_token_path = creds_dir / "gmail_token.json"
    credentials_path = creds_dir / "credentials.json"
    setup_gmail(credentials_path, gmail_token_path)

    # Drive setup (only needed outside Colab)
    click.echo()
    click.echo("-" * 50)
    click.echo("GOOGLE DRIVE AUTHENTICATION")
    click.echo("-" * 50)
    click.echo()

    if is_colab():
        click.echo("Colab detected - Drive authentication handled natively")
    else:
        drive_token_path = creds_dir / "token_do.json"
        setup_drive(credentials_path, drive_token_path)

    # Notification settings
    click.echo()
    click.echo("-" * 50)
    click.echo("NOTIFICATION SERVICE")
    click.echo("-" * 50)
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
    click.echo("-" * 50)
    click.echo("AUTO-APPROVAL SERVICE")
    click.echo("-" * 50)
    click.echo()

    existing_approve = existing_config.get("approve", {})
    existing_jobs = existing_approve.get("jobs", {})
    existing_peers = existing_approve.get("peers", {})

    click.echo("Job Auto-Approval:")
    approve_jobs = click.confirm(
        "  Enable automatic job approval?",
        default=existing_jobs.get("enabled", True),
    )
    jobs_peers_only = False
    required_filenames = []
    allowed_users = []

    if approve_jobs:
        jobs_peers_only = click.confirm(
            "  Only approve jobs from approved peers?",
            default=existing_jobs.get("peers_only", True),
        )

        # Required filenames
        click.echo()
        click.echo("  Job File Validation (leave empty to allow any files):")
        if cli_filenames is not None:
            required_filenames = cli_filenames
            click.echo(f"     Using CLI filenames: {', '.join(required_filenames)}")
        else:
            default_filenames = existing_jobs.get(
                "required_filenames", ["main.py", "params.json"]
            )
            default_str = ",".join(default_filenames) if default_filenames else ""
            filenames_input = click.prompt(
                "     Required filenames (comma-separated)",
                default=default_str,
                show_default=True,
            )
            required_filenames = [
                f.strip() for f in filenames_input.split(",") if f.strip()
            ]

        # Allowed users
        click.echo()
        click.echo("  User Restrictions (leave empty to allow all approved peers):")
        if cli_allowed_users is not None:
            allowed_users = cli_allowed_users
            if allowed_users:
                click.echo(f"     Using CLI allowed users: {', '.join(allowed_users)}")
            else:
                click.echo("     No user restrictions (all approved peers allowed)")
        else:
            default_users = existing_jobs.get("allowed_users", [])
            default_users_str = ",".join(default_users) if default_users else ""
            users_input = click.prompt(
                "     Allowed users (comma-separated emails, empty for all)",
                default=default_users_str,
                show_default=bool(default_users_str),
            )
            allowed_users = [u.strip() for u in users_input.split(",") if u.strip()]

    click.echo()
    click.echo("Peer Auto-Approval:")
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
                "required_filenames": required_filenames,
                "allowed_users": allowed_users,
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
    click.echo("-" * 50)
    click.echo("SETUP COMPLETE")
    click.echo("-" * 50)
    click.echo()
    click.echo(f"Config saved: {config_path}")
    click.echo()
    click.echo("Available commands:")
    click.echo("  syft-bg status     - Show service status")
    click.echo("  syft-bg start      - Start all services")
    click.echo("  syft-bg stop       - Stop all services")
    click.echo("  syft-bg logs <svc> - View service logs")
    click.echo()
    click.echo("To add script hashes for exact code matching:")
    click.echo("  syft-bg hash main.py")
    click.echo(f"  Then edit: {config_path}")
    click.echo()
