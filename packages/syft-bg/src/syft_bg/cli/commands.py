from typing import Optional

import click

from syft_bg.services import ServiceManager, ServiceStatus


def get_status_symbol(status: ServiceStatus) -> str:
    if status == ServiceStatus.RUNNING:
        return "[green]●[/green]"
    elif status == ServiceStatus.STOPPED:
        return "[dim]○[/dim]"
    elif status == ServiceStatus.ERROR:
        return "[red]✗[/red]"
    return "[yellow]?[/yellow]"


def get_status_text(status: ServiceStatus) -> str:
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
def init():
    """Initialize all services with unified setup."""
    from syft_bg.cli.init_flow import run_init_flow

    run_init_flow()


@main.command()
def tui():
    """Launch interactive TUI dashboard."""
    from syft_bg.tui import SyftBgApp

    app = SyftBgApp()
    result = app.run()

    # Handle special exit codes
    if result == 2:
        from syft_bg.cli.init_flow import run_init_flow

        run_init_flow()


if __name__ == "__main__":
    main()
