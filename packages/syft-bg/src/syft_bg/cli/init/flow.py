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

    # Peer approval settings
    approve_peers: bool | None = None
    approved_domains: list[str] | None = None
    approve_interval: int | None = None

    # OAuth/credentials paths
    credentials_path: str | None = None
    gmail_token_path: str | None = None
    drive_token_path: str | None = None


def _print_section(title: str) -> None:
    """Print a section header."""
    click.echo()
    click.echo("-" * 50)
    click.echo(title)
    click.echo("-" * 50)
    click.echo()


def _load_existing_config(config: InitConfig, config_path: Path) -> dict | None:
    """Load existing config and confirm overwrite.

    Returns the existing config dict, or None if the user cancelled.
    An empty dict is returned when no config file exists.
    """
    if not config_path.exists():
        return {}

    with open(config_path) as f:
        existing = yaml.safe_load(f) or {}

    if not config.quiet:
        click.echo(f"Found existing config at {config_path}")

    if not (config.yes or config.quiet):
        if not click.confirm("Update existing configuration?", default=True):
            click.echo("Setup cancelled.")
            return None

    return existing


def _resolve_common_settings(
    config: InitConfig, existing: dict
) -> tuple[str, str] | None:
    """Resolve email and syftbox_root.

    Returns (email, syftbox_root) or None if required values are missing.
    """
    default_email = existing.get("do_email", "")

    if config.email is not None:
        do_email = config.email
        if not config.quiet:
            click.echo(f"Data Owner email address: {do_email}")
    elif config.quiet:
        if not default_email:
            click.echo("Error: --email is required in quiet mode")
            click.echo()
            click.echo("Usage:")
            click.echo("  syft-bg init --email user@example.com --quiet")
            return None
        do_email = default_email
    else:
        do_email = click.prompt(
            "Data Owner email address", default=default_email or None
        )

    default_syftbox = existing.get(
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

    return do_email, syftbox_root


def _setup_auth(config: InitConfig, creds_dir: Path) -> bool:
    """Run Gmail and Drive OAuth setup. Returns False on failure."""
    gmail_token_path = creds_dir / "gmail_token.json"
    credentials_path = creds_dir / "credentials.json"

    if config.gmail_token_path:
        gmail_token_path = Path(config.gmail_token_path).expanduser()
    if config.credentials_path:
        credentials_path = Path(config.credentials_path).expanduser()

    if not setup_gmail(
        credentials_path, gmail_token_path, skip=config.skip_oauth, quiet=config.quiet
    ):
        return False

    if not config.quiet:
        _print_section("GOOGLE DRIVE AUTHENTICATION")

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

    return True


def _resolve_notify_settings(config: InitConfig, existing_notify: dict) -> dict:
    """Resolve notification service settings."""
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

    return {
        "interval": notify_interval,
        "monitor_jobs": notify_jobs,
        "monitor_peers": notify_peers,
    }


def _resolve_approve_settings(config: InitConfig, existing_approve: dict) -> dict:
    """Resolve auto-approval service settings."""
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

    approved_domains: list[str] = []
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

    return {
        "interval": approve_interval,
        "jobs": {
            "enabled": approve_jobs,
            "peers": existing_jobs.get("peers", {}),
        },
        "peers": {
            "enabled": approve_peers,
            "approved_domains": approved_domains,
            "auto_share_datasets": existing_peers.get("auto_share_datasets", []),
        },
    }


def _save_config(
    config_path: Path, do_email: str, syftbox_root: str, notify: dict, approve: dict
) -> None:
    """Build final config dict and write to YAML."""
    final_config = {
        "do_email": do_email,
        "syftbox_root": syftbox_root,
        "notify": notify,
        "approve": approve,
    }

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(final_config, f, default_flow_style=False, sort_keys=False)


def _print_summary(config_path: Path) -> None:
    """Print setup complete summary."""
    _print_section("SETUP COMPLETE")
    click.echo(f"Config saved: {config_path}")
    click.echo()
    click.echo("To approve scripts for data scientists:")
    click.echo(
        "  syft-bg set-script <script.py> --peers email1@example.com email2@example.com"
    )
    click.echo()
    click.echo("Available commands:")
    click.echo("  syft-bg status     - Show service status")
    click.echo("  syft-bg start      - Start all services")
    click.echo("  syft-bg stop       - Stop all services")
    click.echo("  syft-bg logs <svc> - View service logs")
    click.echo()


def run_init_flow(
    config: InitConfig | None = None,
) -> bool:
    """Run unified setup for all background services.

    Args:
        config: InitConfig object with all settings

    Returns:
        True if setup completed successfully, False if cancelled
    """
    if config is None:
        config = InitConfig()

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

    existing = _load_existing_config(config, config_path)
    if existing is None:
        return False

    if not config.quiet:
        _print_section("COMMON SETTINGS")

    common = _resolve_common_settings(config, existing)
    if common is None:
        return False
    do_email, syftbox_root = common

    if not config.quiet:
        _print_section("GMAIL AUTHENTICATION")

    if not _setup_auth(config, creds_dir):
        return False

    if not config.quiet:
        _print_section("NOTIFICATION SERVICE")

    notify = _resolve_notify_settings(config, existing.get("notify", {}))

    if not config.quiet:
        _print_section("AUTO-APPROVAL SERVICE")

    approve = _resolve_approve_settings(config, existing.get("approve", {}))

    _save_config(config_path, do_email, syftbox_root, notify, approve)

    if not config.quiet:
        _print_summary(config_path)

    return True
