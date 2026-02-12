"""Main initialization flow for syft-bg services."""

from dataclasses import dataclass
from pathlib import Path

import click
import yaml

from syft_bg.cli.init.drive_setup import setup_drive
from syft_bg.cli.init.gmail_setup import setup_gmail
from syft_bg.common.config import get_creds_dir
from syft_bg.common.drive import is_colab


@dataclass
class InitConfig:
    """Configuration parameters for syft-bg init flow.

    All parameters are optional. When None, the init flow will either
    prompt the user (interactive mode) or use defaults (quiet mode).
    """

    # Core settings
    email: str | None = None
    syftbox_root: str | None = None

    # Control flags
    yes: bool = False  # Auto-confirm config update
    quiet: bool = False  # Use defaults, no prompts (implies skip_oauth)
    skip_oauth: bool = False  # Skip OAuth setup (tokens must exist)

    # Notification settings (None = prompt or use default)
    notify_jobs: bool | None = None
    notify_peers: bool | None = None
    notify_interval: int | None = None

    # Job approval settings
    approve_jobs: bool | None = None
    jobs_peers_only: bool | None = None
    required_filenames: list[str] | None = None
    allowed_users: list[str] | None = None

    # Peer approval settings
    approve_peers: bool | None = None
    approved_domains: list[str] | None = None
    approve_interval: int | None = None

    # OAuth/credentials paths
    credentials_path: str | None = None
    gmail_token_path: str | None = None
    drive_token_path: str | None = None


def run_init_flow(
    config: InitConfig | None = None,
    # Legacy parameters for backwards compatibility
    cli_email: str | None = None,
    cli_syftbox_root: str | None = None,
    cli_filenames: list[str] | None = None,
    cli_allowed_users: list[str] | None = None,
) -> bool:
    """Run unified setup for all background services.

    Args:
        config: InitConfig object with all settings (preferred)
        cli_email: Data Owner email (legacy, use config.email)
        cli_syftbox_root: SyftBox root directory (legacy, use config.syftbox_root)
        cli_filenames: Required filenames (legacy, use config.required_filenames)
        cli_allowed_users: Allowed users (legacy, use config.allowed_users)

    Returns:
        True if setup completed successfully, False if cancelled
    """
    # Build config from legacy params if not provided
    if config is None:
        config = InitConfig(
            email=cli_email,
            syftbox_root=cli_syftbox_root,
            required_filenames=cli_filenames,
            allowed_users=cli_allowed_users,
        )
    else:
        # Merge legacy params into config if provided
        if cli_email is not None and config.email is None:
            config.email = cli_email
        if cli_syftbox_root is not None and config.syftbox_root is None:
            config.syftbox_root = cli_syftbox_root
        if cli_filenames is not None and config.required_filenames is None:
            config.required_filenames = cli_filenames
        if cli_allowed_users is not None and config.allowed_users is None:
            config.allowed_users = cli_allowed_users
    # quiet mode implies skip_oauth
    if config.quiet:
        config.skip_oauth = True

    if not config.quiet:
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
        if not config.quiet:
            click.echo(f"Found existing config at {config_path}")
        if not (config.yes or config.quiet):
            if not click.confirm("Update existing configuration?", default=True):
                click.echo("Setup cancelled.")
                return False

    # Common settings
    if not config.quiet:
        click.echo()
        click.echo("-" * 50)
        click.echo("COMMON SETTINGS")
        click.echo("-" * 50)
        click.echo()

    default_email = existing_config.get("do_email", "")
    if config.email is not None:
        do_email = config.email
        if not config.quiet:
            click.echo(f"Data Owner email address: {do_email}")
    elif config.quiet:
        # In quiet mode, email is required
        if not default_email:
            click.echo("Error: --email is required in quiet mode")
            click.echo()
            click.echo("Usage:")
            click.echo("  syft-bg init --email user@example.com --quiet")
            return False
        do_email = default_email
    else:
        do_email = click.prompt(
            "Data Owner email address", default=default_email or None
        )

    default_syftbox = existing_config.get(
        "syftbox_root", str(Path.home() / f"SyftBox_{do_email}")
    )
    if config.syftbox_root is not None:
        syftbox_root = config.syftbox_root
        if not config.quiet:
            click.echo(f"SyftBox root directory: {syftbox_root}")
    elif config.quiet:
        syftbox_root = default_syftbox
    else:
        syftbox_root = click.prompt("SyftBox root directory", default=default_syftbox)

    # Gmail setup
    if not config.quiet:
        click.echo()
        click.echo("-" * 50)
        click.echo("GMAIL AUTHENTICATION")
        click.echo("-" * 50)
        click.echo()

    gmail_token_path = creds_dir / "gmail_token.json"
    credentials_path = creds_dir / "credentials.json"

    # Allow custom token/credentials paths from config
    if config.gmail_token_path:
        gmail_token_path = Path(config.gmail_token_path).expanduser()
    if config.credentials_path:
        credentials_path = Path(config.credentials_path).expanduser()

    if not setup_gmail(
        credentials_path, gmail_token_path, skip=config.skip_oauth, quiet=config.quiet
    ):
        return False

    # Drive setup (only needed outside Colab)
    if not config.quiet:
        click.echo()
        click.echo("-" * 50)
        click.echo("GOOGLE DRIVE AUTHENTICATION")
        click.echo("-" * 50)
        click.echo()

    if is_colab():
        if not config.quiet:
            click.echo("Colab detected - Drive authentication handled natively")
    else:
        drive_token_path = creds_dir / "token_do.json"
        if config.drive_token_path:
            drive_token_path = Path(config.drive_token_path).expanduser()

        if not setup_drive(
            credentials_path,
            drive_token_path,
            skip=config.skip_oauth,
            quiet=config.quiet,
        ):
            return False

    # Notification settings
    if not config.quiet:
        click.echo()
        click.echo("-" * 50)
        click.echo("NOTIFICATION SERVICE")
        click.echo("-" * 50)
        click.echo()

    existing_notify = existing_config.get("notify", {})

    if config.notify_jobs is not None:
        notify_jobs = config.notify_jobs
    elif config.quiet:
        notify_jobs = existing_notify.get("monitor_jobs", True)
    else:
        notify_jobs = click.confirm(
            "Enable email notifications for new jobs?",
            default=existing_notify.get("monitor_jobs", True),
        )

    if config.notify_peers is not None:
        notify_peers = config.notify_peers
    elif config.quiet:
        notify_peers = existing_notify.get("monitor_peers", True)
    else:
        notify_peers = click.confirm(
            "Enable email notifications for peer requests?",
            default=existing_notify.get("monitor_peers", True),
        )

    if config.notify_interval is not None:
        notify_interval = config.notify_interval
    elif config.quiet:
        notify_interval = existing_notify.get("interval", 30)
    else:
        notify_interval = click.prompt(
            "Check interval (seconds)",
            type=int,
            default=existing_notify.get("interval", 30),
        )

    # Auto-approval settings
    if not config.quiet:
        click.echo()
        click.echo("-" * 50)
        click.echo("AUTO-APPROVAL SERVICE")
        click.echo("-" * 50)
        click.echo()

    existing_approve = existing_config.get("approve", {})
    existing_jobs = existing_approve.get("jobs", {})
    existing_peers = existing_approve.get("peers", {})

    if not config.quiet:
        click.echo("Job Auto-Approval:")

    if config.approve_jobs is not None:
        approve_jobs = config.approve_jobs
    elif config.quiet:
        approve_jobs = existing_jobs.get("enabled", True)
    else:
        approve_jobs = click.confirm(
            "  Enable automatic job approval?",
            default=existing_jobs.get("enabled", True),
        )

    jobs_peers_only = False
    required_filenames = []
    allowed_users = []

    if approve_jobs:
        if config.jobs_peers_only is not None:
            jobs_peers_only = config.jobs_peers_only
        elif config.quiet:
            jobs_peers_only = existing_jobs.get("peers_only", True)
        else:
            jobs_peers_only = click.confirm(
                "  Only approve jobs from approved peers?",
                default=existing_jobs.get("peers_only", True),
            )

        # Required filenames
        if not config.quiet:
            click.echo()
            click.echo("  Job File Validation (leave empty to allow any files):")

        if config.required_filenames is not None:
            required_filenames = config.required_filenames
            if not config.quiet:
                click.echo(f"     Using CLI filenames: {', '.join(required_filenames)}")
        elif config.quiet:
            required_filenames = existing_jobs.get(
                "required_filenames", ["main.py", "params.json"]
            )
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
        if not config.quiet:
            click.echo()
            click.echo("  User Restrictions (leave empty to allow all approved peers):")

        if config.allowed_users is not None:
            allowed_users = config.allowed_users
            if not config.quiet:
                if allowed_users:
                    click.echo(
                        f"     Using CLI allowed users: {', '.join(allowed_users)}"
                    )
                else:
                    click.echo("     No user restrictions (all approved peers allowed)")
        elif config.quiet:
            allowed_users = existing_jobs.get("allowed_users", [])
        else:
            default_users = existing_jobs.get("allowed_users", [])
            default_users_str = ",".join(default_users) if default_users else ""
            users_input = click.prompt(
                "     Allowed users (comma-separated emails, empty for all)",
                default=default_users_str,
                show_default=bool(default_users_str),
            )
            allowed_users = [u.strip() for u in users_input.split(",") if u.strip()]

    if not config.quiet:
        click.echo()
        click.echo("Peer Auto-Approval:")

    if config.approve_peers is not None:
        approve_peers = config.approve_peers
    elif config.quiet:
        approve_peers = existing_peers.get("enabled", False)
    else:
        approve_peers = click.confirm(
            "  Enable automatic peer approval?",
            default=existing_peers.get("enabled", False),
        )

    approved_domains = []
    if approve_peers:
        if config.approved_domains is not None:
            approved_domains = config.approved_domains
        elif config.quiet:
            approved_domains = existing_peers.get("approved_domains", ["openmined.org"])
        else:
            default_domains = ",".join(
                existing_peers.get("approved_domains", ["openmined.org"])
            )
            domains_input = click.prompt(
                "  Approved domains (comma-separated)", default=default_domains
            )
            approved_domains = [
                d.strip() for d in domains_input.split(",") if d.strip()
            ]

    if config.approve_interval is not None:
        approve_interval = config.approve_interval
    elif config.quiet:
        approve_interval = existing_approve.get("interval", 5)
    else:
        approve_interval = click.prompt(
            "Check interval (seconds)",
            type=int,
            default=existing_approve.get("interval", 5),
        )

    # Build config dict (using 'final_config' to avoid shadowing the InitConfig 'config')
    final_config = {
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
        yaml.dump(final_config, f, default_flow_style=False, sort_keys=False)

    if not config.quiet:
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

    return True
