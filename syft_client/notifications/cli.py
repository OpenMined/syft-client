"""
CLI for SyftBox Notification Daemon.

Usage:
    # First time setup (creates config + tokens)
    syft-notify init

    # Background daemon commands
    syft-notify start            # Start daemon in background
    syft-notify stop             # Stop daemon
    syft-notify restart          # Restart daemon
    syft-notify status           # Check daemon status
    syft-notify logs             # View logs
    syft-notify logs --follow    # Follow logs (tail -f)

    # Foreground mode (for debugging)
    syft-notify run [--config PATH] [--interval SECONDS]
"""

import signal
import sys
from pathlib import Path
from typing import Optional

import click
import yaml


# Default paths
DEFAULT_CREDS_DIR = Path.home() / ".syft-creds"
DEFAULT_CONFIG_PATH = DEFAULT_CREDS_DIR / "daemon.yaml"
DEFAULT_GMAIL_TOKEN = DEFAULT_CREDS_DIR / "gmail_token.json"
DEFAULT_DRIVE_TOKEN = DEFAULT_CREDS_DIR / "token_do.json"
DEFAULT_CREDENTIALS = DEFAULT_CREDS_DIR / "credentials.json"


def find_credentials_json() -> Optional[Path]:
    """Find credentials.json in standard locations."""
    locations = [
        DEFAULT_CREDENTIALS,
        Path.home() / ".syft-creds" / "credentials.json",
        Path.cwd() / "credentials.json",
    ]
    for loc in locations:
        if loc.exists():
            return loc
    return None


def find_drive_token() -> Optional[Path]:
    """Find existing Drive token in standard locations."""
    locations = [
        DEFAULT_DRIVE_TOKEN,
        Path.home() / ".syft-creds" / "token_do.json",
    ]

    # Also check syft-client credentials directory
    try:
        from syft_client import CREDENTIALS_DIR

        locations.append(CREDENTIALS_DIR / "token_do.json")
        locations.append(CREDENTIALS_DIR / "token.json")
    except ImportError:
        # syft_client may not be installed, skip adding its credential locations
        pass

    for loc in locations:
        if loc.exists():
            return loc
    return None


def run_gmail_oauth(credentials_path: Path, token_path: Path) -> bool:
    """Run Gmail OAuth flow and save token."""
    try:
        from .gmail_auth import GmailAuth

        click.echo("📧 Setting up Gmail authentication...")
        click.echo(f"   Credentials: {credentials_path}")
        click.echo(f"   Token will be saved to: {token_path}")
        click.echo()

        auth = GmailAuth()
        credentials = auth.setup_auth(str(credentials_path))

        # Save token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json())

        click.echo(f"✅ Gmail token saved: {token_path}")
        return True

    except Exception as e:
        click.echo(f"❌ Gmail setup failed: {e}", err=True)
        return False


def run_drive_oauth(credentials_path: Path, token_path: Path) -> bool:
    """Run Google Drive OAuth flow and save token."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        SCOPES = ["https://www.googleapis.com/auth/drive"]

        click.echo("🔑 Setting up Google Drive authentication...")
        click.echo(f"   Credentials: {credentials_path}")
        click.echo(f"   Token will be saved to: {token_path}")
        click.echo()

        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        credentials = flow.run_local_server(port=0)

        # Save token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        with open(token_path, "w") as f:
            f.write(credentials.to_json())

        click.echo(f"✅ Drive token saved: {token_path}")
        return True

    except Exception as e:
        click.echo(f"❌ Drive setup failed: {e}", err=True)
        return False


def _resolve_config_path(config: Optional[str]) -> Path:
    """Resolve config path, check if exists."""
    config_path = Path(config).expanduser() if config else DEFAULT_CONFIG_PATH

    if not config_path.exists():
        click.echo(f"❌ Config file not found: {config_path}", err=True)
        click.echo()
        click.echo("Run setup first:")
        click.echo("    syft-notify init")
        sys.exit(1)

    return config_path


@click.group()
def main():
    """
    SyftBox Notification Daemon.

    Monitors Google Drive for job/peer events and sends email notifications.
    """
    pass


@main.command()
def init():
    """
    Interactive setup to create config and OAuth tokens.

    Creates:
      - ~/.syft-creds/daemon.yaml (config)
      - ~/.syft-creds/gmail_token.json (Gmail OAuth)
      - ~/.syft-creds/token_do.json (Drive OAuth)
    """
    click.echo("🔧 SyftBox Notification Daemon Setup")
    click.echo("=" * 50)
    click.echo()

    # Step 1: Find or ask for credentials.json
    creds_path = find_credentials_json()
    if creds_path:
        click.echo(f"✅ Found credentials.json: {creds_path}")
    else:
        click.echo("❌ credentials.json not found in standard locations.")
        click.echo()
        click.echo("To get credentials.json:")
        click.echo("  1. Go to Google Cloud Console → APIs & Services → Credentials")
        click.echo("  2. Create OAuth 2.0 Client ID (Desktop app)")
        click.echo("  3. Download as credentials.json")
        click.echo()
        creds_input = click.prompt(
            "Enter path to credentials.json",
            type=click.Path(exists=True),
        )
        creds_path = Path(creds_input).expanduser()

    click.echo()

    # Step 2: Ask for DO email
    do_email = click.prompt("Enter your Data Owner email address")

    # Step 3: Determine SyftBox root
    default_syftbox = Path.home() / f"SyftBox_{do_email}"
    syftbox_root = click.prompt(
        "SyftBox root directory",
        default=str(default_syftbox),
    )

    click.echo()
    click.echo("-" * 50)
    click.echo()

    # Step 4: Setup Drive token if needed
    existing_drive_token = find_drive_token()
    if existing_drive_token:
        click.echo(f"✅ Found Drive token: {existing_drive_token}")
        drive_token_path = existing_drive_token
    else:
        click.echo("📁 Google Drive token not found. Setting up...")
        if run_drive_oauth(creds_path, DEFAULT_DRIVE_TOKEN):
            drive_token_path = DEFAULT_DRIVE_TOKEN
        else:
            click.echo("⚠️  Drive setup failed. You can retry later.", err=True)
            drive_token_path = DEFAULT_DRIVE_TOKEN

    click.echo()

    # Step 5: Setup Gmail token if needed
    if DEFAULT_GMAIL_TOKEN.exists():
        click.echo(f"✅ Gmail token exists: {DEFAULT_GMAIL_TOKEN}")
    else:
        click.echo("📧 Gmail token not found. Setting up...")
        if not run_gmail_oauth(creds_path, DEFAULT_GMAIL_TOKEN):
            click.echo("⚠️  Gmail setup failed. You can retry later.", err=True)

    click.echo()
    click.echo("-" * 50)
    click.echo()

    # Step 6: Create config file
    config = {
        "do_email": do_email,
        "syftbox_root": syftbox_root,
        "drive_token_path": str(drive_token_path),
        "gmail_token_path": str(DEFAULT_GMAIL_TOKEN),
        "interval": 30,
    }

    DEFAULT_CREDS_DIR.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    click.echo(f"✅ Config file created: {DEFAULT_CONFIG_PATH}")
    click.echo()
    click.echo("=" * 50)
    click.echo("🎉 Setup complete!")
    click.echo()
    click.echo("To start the notification daemon in background, run:")
    click.echo()
    click.echo("    syft-notify start")
    click.echo()


@main.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(),
    default=None,
    help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=None,
    help="Check interval in seconds (overrides config)",
)
def start(config: Optional[str], interval: Optional[int]):
    """
    Start daemon in background.

    The daemon will continue running even after you close the terminal.
    """
    config_path = _resolve_config_path(config)

    from .daemon_manager import DaemonManager

    manager = DaemonManager(config_path)
    manager.start(interval)


@main.command()
def stop():
    """Stop the running daemon."""
    from .daemon_manager import DaemonManager

    manager = DaemonManager(DEFAULT_CONFIG_PATH)
    manager.stop()


@main.command()
def status():
    """Check if daemon is running and show recent activity."""
    from .daemon_manager import DaemonManager

    manager = DaemonManager(DEFAULT_CONFIG_PATH)
    manager.status()


@main.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(),
    default=None,
    help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=None,
    help="Check interval in seconds (overrides config)",
)
def restart(config: Optional[str], interval: Optional[int]):
    """Restart the daemon."""
    config_path = _resolve_config_path(config)

    from .daemon_manager import DaemonManager

    manager = DaemonManager(config_path)
    manager.restart(interval)


@main.command()
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Follow log output (like tail -f)",
)
@click.option(
    "--lines",
    "-n",
    type=int,
    default=50,
    help="Number of lines to show (default: 50)",
)
def logs(follow: bool, lines: int):
    """View daemon logs."""
    from .daemon_manager import DaemonManager

    manager = DaemonManager(DEFAULT_CONFIG_PATH)
    manager.logs(follow=follow, lines=lines)


@main.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(),
    default=None,
    help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
)
@click.option(
    "--interval",
    "-i",
    type=int,
    default=None,
    help="Check interval in seconds (overrides config)",
)
@click.option(
    "--jobs-only",
    is_flag=True,
    help="Only monitor jobs (skip peer monitoring)",
)
@click.option(
    "--peers-only",
    is_flag=True,
    help="Only monitor peers (skip job monitoring)",
)
@click.option(
    "--once",
    is_flag=True,
    help="Run a single check and exit",
)
def run(
    config: Optional[str],
    interval: Optional[int],
    jobs_only: bool,
    peers_only: bool,
    once: bool,
):
    """
    Run daemon in foreground (for debugging).

    Unlike 'start', this keeps the daemon attached to your terminal.
    Press Ctrl+C to stop.
    """
    config_path = _resolve_config_path(config)

    from .monitor import NotificationMonitor

    # Determine monitor type
    monitor_type = None
    if jobs_only and peers_only:
        click.echo("Error: Cannot use both --jobs-only and --peers-only", err=True)
        sys.exit(1)
    elif jobs_only:
        monitor_type = "jobs"
    elif peers_only:
        monitor_type = "peers"

    try:
        # Create monitor from config
        monitor = NotificationMonitor.from_config(str(config_path), interval=interval)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(f"Config error: {e}", err=True)
        sys.exit(1)

    if once:
        # Single check mode
        click.echo("Running single check...")
        monitor.check(monitor_type)
        click.echo("Done.")
        return

    # Set up signal handlers for graceful shutdown
    def handle_signal(signum, frame):
        click.echo("\nReceived shutdown signal...")
        monitor._stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Run the daemon (blocking)
    try:
        monitor.run(monitor_type)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
