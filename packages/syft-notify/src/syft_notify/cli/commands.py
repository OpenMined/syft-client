import signal
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from syft_notify.core.config import get_default_paths

DEFAULT_PATHS = get_default_paths()


def _resolve_config_path(config: Optional[str]) -> Path:
    config_path = Path(config).expanduser() if config else DEFAULT_PATHS["config"]

    if not config_path.exists():
        click.echo(f"❌ Config file not found: {config_path}", err=True)
        click.echo("Run 'syft-notify init' first.")
        sys.exit(1)

    return config_path


@click.group()
def main():
    """SyftBox Notification Daemon."""
    pass


@main.command()
def init():
    """Interactive setup to create config and OAuth tokens."""
    from syft_notify.gmail import GmailAuth

    click.echo("🔧 SyftBox Notification Daemon Setup")
    click.echo("=" * 50)
    click.echo()

    creds_path = DEFAULT_PATHS["credentials"]
    if not creds_path.exists():
        click.echo(f"❌ credentials.json not found at {creds_path}")
        click.echo()
        click.echo("To get credentials.json:")
        click.echo("  1. Go to Google Cloud Console → APIs & Services → Credentials")
        click.echo("  2. Create OAuth 2.0 Client ID (Desktop app)")
        click.echo("  3. Download as credentials.json")
        click.echo(f"  4. Place it at: {creds_path}")
        click.echo()
        creds_input = click.prompt(
            "Or enter path to credentials.json", type=click.Path(exists=True)
        )
        creds_path = Path(creds_input).expanduser()

    do_email = click.prompt("Enter your Data Owner email address")

    default_syftbox = Path.home() / f"SyftBox_{do_email}"
    syftbox_root = click.prompt("SyftBox root directory", default=str(default_syftbox))

    click.echo()

    # Setup Gmail token
    gmail_token = DEFAULT_PATHS["gmail_token"]
    if gmail_token.exists():
        click.echo(f"✅ Gmail token exists: {gmail_token}")
    else:
        click.echo("📧 Setting up Gmail authentication...")
        try:
            auth = GmailAuth()
            credentials = auth.setup_auth(creds_path)
            gmail_token.parent.mkdir(parents=True, exist_ok=True)
            gmail_token.write_text(credentials.to_json())
            click.echo(f"✅ Gmail token saved: {gmail_token}")
        except Exception as e:
            click.echo(f"⚠️  Gmail setup failed: {e}", err=True)

    click.echo()

    # Create config
    config = {
        "email": do_email,
        "syftbox_root": syftbox_root,
        "notify": {
            "interval": 30,
            "monitor_jobs": True,
            "monitor_peers": True,
        },
    }

    config_path = DEFAULT_PATHS["config"]
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    click.echo(f"✅ Config saved: {config_path}")
    click.echo()
    click.echo("🎉 Setup complete! Run 'syft-notify start' to begin.")


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.option("--interval", "-i", type=int, help="Check interval in seconds")
def start(config: Optional[str], interval: Optional[int]):
    """Start daemon in background."""
    config_path = _resolve_config_path(config)

    from syft_notify.cli.daemon import DaemonManager

    manager = DaemonManager(config_path)
    manager.start(interval)


@main.command()
def stop():
    """Stop the running daemon."""
    from syft_notify.cli.daemon import DaemonManager

    manager = DaemonManager(DEFAULT_PATHS["config"])
    manager.stop()


@main.command()
def status():
    """Check daemon status."""
    from syft_notify.cli.daemon import DaemonManager

    manager = DaemonManager(DEFAULT_PATHS["config"])
    manager.status()


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.option("--interval", "-i", type=int, help="Check interval in seconds")
def restart(config: Optional[str], interval: Optional[int]):
    """Restart the daemon."""
    config_path = _resolve_config_path(config)

    from syft_notify.cli.daemon import DaemonManager

    manager = DaemonManager(config_path)
    manager.restart(interval)


@main.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show")
def logs(follow: bool, lines: int):
    """View daemon logs."""
    from syft_notify.cli.daemon import DaemonManager

    manager = DaemonManager(DEFAULT_PATHS["config"])
    manager.logs(follow=follow, lines=lines)


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.option("--interval", "-i", type=int, help="Check interval in seconds")
@click.option("--jobs-only", is_flag=True, help="Only monitor jobs")
@click.option("--peers-only", is_flag=True, help="Only monitor peers")
@click.option("--once", is_flag=True, help="Run single check and exit")
def run(
    config: Optional[str],
    interval: Optional[int],
    jobs_only: bool,
    peers_only: bool,
    once: bool,
):
    """Run daemon in foreground (for debugging)."""
    config_path = _resolve_config_path(config)

    from syft_notify.orchestrator import NotificationOrchestrator

    monitor_type = None
    if jobs_only and peers_only:
        click.echo("Error: Cannot use both --jobs-only and --peers-only", err=True)
        sys.exit(1)
    elif jobs_only:
        monitor_type = "jobs"
    elif peers_only:
        monitor_type = "peers"

    try:
        orchestrator = NotificationOrchestrator.from_config(
            str(config_path), interval=interval
        )
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if once:
        click.echo("Running single check...")
        orchestrator.check(monitor_type)
        click.echo("Done.")
        return

    def handle_signal(signum, frame):
        orchestrator._stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    orchestrator.run(monitor_type)


if __name__ == "__main__":
    main()
