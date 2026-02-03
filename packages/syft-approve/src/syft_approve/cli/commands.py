import hashlib
import signal
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from syft_approve.core.config import get_default_paths

DEFAULT_PATHS = get_default_paths()


def _resolve_config_path(config: Optional[str]) -> Path:
    config_path = Path(config).expanduser() if config else DEFAULT_PATHS.config

    if not config_path.exists():
        click.echo(f"❌ Config file not found: {config_path}", err=True)
        click.echo("Run 'syft-approve init' first.")
        sys.exit(1)

    return config_path


@click.group()
def main():
    """SyftBox Auto-Approval Daemon."""
    pass


@main.command()
def init():
    """Create initial config file."""
    click.echo("🔧 SyftBox Auto-Approval Daemon Setup")
    click.echo("=" * 50)
    click.echo()

    do_email = click.prompt("Enter your Data Owner email address")

    default_syftbox = Path.home() / f"SyftBox_{do_email}"
    syftbox_root = click.prompt("SyftBox root directory", default=str(default_syftbox))

    # Ask about job auto-approval
    click.echo()
    click.echo("📋 Job Auto-Approval Settings")
    jobs_enabled = click.confirm("Enable job auto-approval?", default=True)
    peers_only = click.confirm("Only approve jobs from peers?", default=True)

    # Ask about peer auto-approval
    click.echo()
    click.echo("🤝 Peer Auto-Approval Settings")
    peers_enabled = click.confirm("Enable peer auto-approval?", default=False)
    approved_domains = []
    if peers_enabled:
        domains_input = click.prompt(
            "Approved domains (comma-separated)", default="openmined.org"
        )
        approved_domains = [d.strip() for d in domains_input.split(",") if d.strip()]

    click.echo()

    # Create config
    config = {
        "do_email": do_email,
        "syftbox_root": syftbox_root,
        "approve": {
            "interval": 5,
            "jobs": {
                "enabled": jobs_enabled,
                "peers_only": peers_only,
                "required_scripts": {},
                "required_filenames": [],
                "allowed_users": [],
            },
            "peers": {
                "enabled": peers_enabled,
                "approved_domains": approved_domains,
                "auto_share_datasets": [],
            },
        },
    }

    config_path = DEFAULT_PATHS.config
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    click.echo(f"✅ Config saved: {config_path}")
    click.echo()
    click.echo("Edit the config file to add:")
    click.echo("  - required_scripts: script hashes (use 'syft-approve hash <file>')")
    click.echo("  - required_filenames: list of required files")
    click.echo()
    click.echo("Then run 'syft-approve start' to begin.")


@main.command()
@click.argument("file", type=click.Path(exists=True))
def hash(file: str):
    """Generate hash for a script file."""
    file_path = Path(file).expanduser()
    content = file_path.read_text(encoding="utf-8")
    full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    short_hash = full_hash[:16]
    click.echo(f"sha256:{short_hash}")
    click.echo()
    click.echo("Add to config.yaml:")
    click.echo("  required_scripts:")
    click.echo(f"    {file_path.name}: sha256:{short_hash}")


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.option("--interval", "-i", type=int, help="Check interval in seconds")
def start(config: Optional[str], interval: Optional[int]):
    """Start daemon in background."""
    config_path = _resolve_config_path(config)

    from syft_approve.cli.daemon import DaemonManager

    manager = DaemonManager(config_path)
    manager.start(interval)


@main.command()
def stop():
    """Stop the running daemon."""
    from syft_approve.cli.daemon import DaemonManager

    manager = DaemonManager(DEFAULT_PATHS.config)
    manager.stop()


@main.command()
def status():
    """Check daemon status."""
    from syft_approve.cli.daemon import DaemonManager

    manager = DaemonManager(DEFAULT_PATHS.config)
    manager.status()


@main.command()
@click.option("--config", "-c", type=click.Path(), help="Path to config file")
@click.option("--interval", "-i", type=int, help="Check interval in seconds")
def restart(config: Optional[str], interval: Optional[int]):
    """Restart the daemon."""
    config_path = _resolve_config_path(config)

    from syft_approve.cli.daemon import DaemonManager

    manager = DaemonManager(config_path)
    manager.restart(interval)


@main.command()
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show")
def logs(follow: bool, lines: int):
    """View daemon logs."""
    from syft_approve.cli.daemon import DaemonManager

    manager = DaemonManager(DEFAULT_PATHS.config)
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

    from syft_approve.orchestrator import ApprovalOrchestrator

    monitor_type = None
    if jobs_only and peers_only:
        click.echo("Error: Cannot use both --jobs-only and --peers-only", err=True)
        sys.exit(1)
    elif jobs_only:
        monitor_type = "jobs"
    elif peers_only:
        monitor_type = "peers"

    try:
        orchestrator = ApprovalOrchestrator.from_config(
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
