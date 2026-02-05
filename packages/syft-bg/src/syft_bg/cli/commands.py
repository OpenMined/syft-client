"""CLI commands for syft-bg."""

import hashlib
from typing import Optional

import click

from syft_bg.services import ServiceManager, ServiceStatus


def get_status_text(status: ServiceStatus) -> str:
    """Get human-readable status text."""
    if status == ServiceStatus.RUNNING:
        return "Running"
    elif status == ServiceStatus.STOPPED:
        return "Stopped"
    elif status == ServiceStatus.ERROR:
        return "Error"
    return "Unknown"


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    """SyftBox Background Services Manager."""
    if ctx.invoked_subcommand is None:
        # Default to TUI dashboard if no command given
        ctx.invoke(tui)


@main.command()
def status():
    """Show status of all services."""
    manager = ServiceManager()
    all_status = manager.get_all_status()

    click.echo()
    click.echo("SYFT BACKGROUND SERVICES")
    click.echo("=" * 50)
    click.echo()
    click.echo(f"{'SERVICE':<12} {'STATUS':<12} {'PID':<10} {'DESCRIPTION'}")
    click.echo("-" * 50)

    for name, info in all_status.items():
        service = manager.get_service(name)
        status_text = get_status_text(info.status)
        pid_text = str(info.pid) if info.pid else "-"

        if info.status == ServiceStatus.RUNNING:
            click.echo(
                f"{name:<12} {'● ' + status_text:<12} {pid_text:<10} {service.description}"
            )
        else:
            click.echo(
                f"{name:<12} {'○ ' + status_text:<12} {pid_text:<10} {service.description}"
            )

    click.echo()


@main.command()
@click.argument("service", required=False)
def start(service: Optional[str]):
    """Start services. If SERVICE specified, start only that service."""
    manager = ServiceManager()

    if service:
        if service not in manager.list_services():
            click.echo(f"Unknown service: {service}", err=True)
            click.echo(f"Available: {', '.join(manager.list_services())}")
            return

        click.echo(f"Starting {service}...")
        success, msg = manager.start_service(service)
        if success:
            click.echo(f"✅ {msg}")
        else:
            click.echo(f"❌ {msg}", err=True)
    else:
        click.echo("Starting all services...")
        results = manager.start_all()
        for name, (success, msg) in results.items():
            if success:
                click.echo(f"✅ {name}: {msg}")
            else:
                click.echo(f"❌ {name}: {msg}")


@main.command()
@click.argument("service", required=False)
def stop(service: Optional[str]):
    """Stop services. If SERVICE specified, stop only that service."""
    manager = ServiceManager()

    if service:
        if service not in manager.list_services():
            click.echo(f"Unknown service: {service}", err=True)
            click.echo(f"Available: {', '.join(manager.list_services())}")
            return

        click.echo(f"Stopping {service}...")
        success, msg = manager.stop_service(service)
        if success:
            click.echo(f"✅ {msg}")
        else:
            click.echo(f"❌ {msg}", err=True)
    else:
        click.echo("Stopping all services...")
        results = manager.stop_all()
        for name, (success, msg) in results.items():
            if success:
                click.echo(f"✅ {name}: {msg}")
            else:
                click.echo(f"❌ {name}: {msg}")


@main.command()
@click.argument("service", required=False)
def restart(service: Optional[str]):
    """Restart services. If SERVICE specified, restart only that service."""
    manager = ServiceManager()

    if service:
        if service not in manager.list_services():
            click.echo(f"Unknown service: {service}", err=True)
            click.echo(f"Available: {', '.join(manager.list_services())}")
            return

        click.echo(f"Restarting {service}...")
        success, msg = manager.restart_service(service)
        if success:
            click.echo(f"✅ {msg}")
        else:
            click.echo(f"❌ {msg}", err=True)
    else:
        click.echo("Restarting all services...")
        for name in manager.list_services():
            success, msg = manager.restart_service(name)
            if success:
                click.echo(f"✅ {name}: {msg}")
            else:
                click.echo(f"❌ {name}: {msg}")


@main.command()
@click.argument("service")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option("--lines", "-n", type=int, default=50, help="Number of lines to show")
def logs(service: str, follow: bool, lines: int):
    """View logs for a service."""
    import subprocess

    manager = ServiceManager()

    if service not in manager.list_services():
        click.echo(f"Unknown service: {service}", err=True)
        click.echo(f"Available: {', '.join(manager.list_services())}")
        return

    svc = manager.get_service(service)

    if not svc.log_file.exists():
        click.echo(f"Log file not found: {svc.log_file}")
        return

    if follow:
        click.echo(f"Following {svc.log_file} (Ctrl+C to stop)...")
        try:
            subprocess.run(["tail", "-f", str(svc.log_file)])
        except KeyboardInterrupt:
            click.echo("\nStopped")
    else:
        log_lines = manager.get_logs(service, lines)
        if log_lines:
            click.echo(f"Last {len(log_lines)} lines from {service}:")
            click.echo("-" * 50)
            for line in log_lines:
                click.echo(line)
        else:
            click.echo("No logs available")


@main.command()
@click.option(
    "--filenames",
    "-f",
    help="Required filenames (comma-separated). Default: main.py,params.json",
)
@click.option(
    "--allowed-users",
    "-u",
    help="Allowed users (comma-separated). Empty means all peers allowed.",
)
def init(filenames: str | None, allowed_users: str | None):
    """Initialize all services with unified setup.

    Examples:

      syft-bg init

      syft-bg init --filenames main.py,params.json

      syft-bg init -f main.py,params.json -u alice@example.com
    """
    from syft_bg.cli.init import run_init_flow

    # Parse CLI options
    parsed_filenames = None
    if filenames:
        parsed_filenames = [f.strip() for f in filenames.split(",") if f.strip()]

    parsed_allowed_users = None
    if allowed_users is not None:
        parsed_allowed_users = [
            u.strip() for u in allowed_users.split(",") if u.strip()
        ]

    run_init_flow(
        cli_filenames=parsed_filenames,
        cli_allowed_users=parsed_allowed_users,
    )


@main.command()
def tui():
    """Launch interactive TUI dashboard."""
    from syft_bg.tui import SyftBgApp

    app = SyftBgApp()
    result = app.run()

    # Handle special exit codes
    if result == 2:
        from syft_bg.cli.init import run_init_flow

        run_init_flow()


@main.command()
@click.option(
    "--service",
    "-s",
    type=click.Choice(["notify", "approve"]),
    required=True,
    help="Service to run",
)
@click.option("--once", is_flag=True, help="Run single check cycle and exit")
def run(service: str, once: bool):
    """Run a service in foreground.

    This command is used internally by 'syft-bg start' to spawn services
    as subprocesses. You can also use it directly for debugging.

    Examples:

      syft-bg run --service notify

      syft-bg run --service approve --once
    """
    if service == "notify":
        from syft_bg.notify import NotificationOrchestrator

        try:
            orchestrator = NotificationOrchestrator.from_config()
            if once:
                orchestrator.check()
            else:
                orchestrator.run()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Run 'syft-bg init' first to configure the service.", err=True)
            raise SystemExit(1)

    elif service == "approve":
        from syft_bg.approve import ApprovalOrchestrator

        try:
            orchestrator = ApprovalOrchestrator.from_config()
            if once:
                orchestrator.check()
            else:
                orchestrator.run()
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            click.echo("Run 'syft-bg init' first to configure the service.", err=True)
            raise SystemExit(1)


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--length",
    "-l",
    type=int,
    default=16,
    help="Hash length (default: 16 characters)",
)
def hash(file: str, length: int):
    """Generate SHA256 hash for a script file.

    Use this to create hash values for the 'required_scripts' config option.

    Examples:

      syft-bg hash main.py

      syft-bg hash main.py --length 8

    Output format: sha256:<hash>
    """
    from pathlib import Path

    file_path = Path(file)
    try:
        content = file_path.read_text(encoding="utf-8")
        full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        short_hash = full_hash[:length]
        click.echo(f"sha256:{short_hash}")
    except Exception as e:
        click.echo(f"Error reading file: {e}", err=True)
        raise SystemExit(1)


@main.command()
def install():
    """Install syft-bg as a systemd user service.

    This enables syft-bg to start automatically on login.

    Examples:

      syft-bg install

    After installation:

      systemctl --user start syft-bg    # Start now
      systemctl --user status syft-bg   # Check status
      systemctl --user stop syft-bg     # Stop
    """
    from syft_bg.systemd import install_service

    click.echo("Installing syft-bg systemd user service...")
    success, msg = install_service()

    if success:
        click.echo(f"✅ {msg}")
        click.echo()
        click.echo("To start the service now:")
        click.echo("  systemctl --user start syft-bg")
        click.echo()
        click.echo("To check status:")
        click.echo("  systemctl --user status syft-bg")
    else:
        click.echo(f"❌ {msg}", err=True)
        raise SystemExit(1)


@main.command()
def uninstall():
    """Uninstall syft-bg systemd user service.

    This stops the service and removes it from systemd.

    Example:

      syft-bg uninstall
    """
    from syft_bg.systemd import uninstall_service

    click.echo("Uninstalling syft-bg systemd user service...")
    success, msg = uninstall_service()

    if success:
        click.echo(f"✅ {msg}")
    else:
        click.echo(f"❌ {msg}", err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
