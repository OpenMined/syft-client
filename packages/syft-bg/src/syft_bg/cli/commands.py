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
# Core settings
@click.option(
    "--email",
    "-e",
    help="Data Owner email address.",
)
@click.option(
    "--syftbox-root",
    "-r",
    help="SyftBox root directory.",
)
# Control flags
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Auto-confirm update of existing configuration.",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    help="Run with defaults, no prompts. Implies --skip-oauth.",
)
@click.option(
    "--skip-oauth",
    is_flag=True,
    help="Skip OAuth setup. Tokens must already exist.",
)
# Notification settings
@click.option(
    "--notify-jobs/--no-notify-jobs",
    default=None,
    help="Enable/disable email notifications for new jobs.",
)
@click.option(
    "--notify-peers/--no-notify-peers",
    default=None,
    help="Enable/disable email notifications for peer requests.",
)
@click.option(
    "--notify-interval",
    type=int,
    help="Notification check interval in seconds. Default: 30.",
)
# Job approval settings
@click.option(
    "--approve-jobs/--no-approve-jobs",
    default=None,
    help="Enable/disable automatic job approval.",
)
# Peer approval settings
@click.option(
    "--approve-peers/--no-approve-peers",
    default=None,
    help="Enable/disable automatic peer approval.",
)
@click.option(
    "--approved-domains",
    help="Approved domains for peer auto-approval (comma-separated).",
)
@click.option(
    "--approve-interval",
    type=int,
    help="Approval check interval in seconds. Default: 5.",
)
# OAuth/credentials paths
@click.option(
    "--credentials-path",
    type=click.Path(),
    help="Path to credentials.json for OAuth.",
)
@click.option(
    "--gmail-token",
    type=click.Path(),
    help="Path to pre-existing Gmail token.",
)
@click.option(
    "--drive-token",
    type=click.Path(),
    help="Path to pre-existing Drive token.",
)
def init(
    email: str | None,
    syftbox_root: str | None,
    yes: bool,
    quiet: bool,
    skip_oauth: bool,
    notify_jobs: bool | None,
    notify_peers: bool | None,
    notify_interval: int | None,
    approve_jobs: bool | None,
    approve_peers: bool | None,
    approved_domains: str | None,
    approve_interval: int | None,
    credentials_path: str | None,
    gmail_token: str | None,
    drive_token: str | None,
):
    """Initialize all services with unified setup.

    Examples:

      syft-bg init

      syft-bg init --email user@example.com

      syft-bg init -e user@example.com -r ~/SyftBox --quiet --skip-oauth

      syft-bg init --notify-jobs --no-notify-peers --approve-jobs
    """
    from syft_bg.cli.init import InitConfig, run_init_flow

    parsed_approved_domains = None
    if approved_domains:
        parsed_approved_domains = [
            d.strip() for d in approved_domains.split(",") if d.strip()
        ]

    config = InitConfig(
        email=email,
        syftbox_root=syftbox_root,
        yes=yes,
        quiet=quiet,
        skip_oauth=skip_oauth,
        notify_jobs=notify_jobs,
        notify_peers=notify_peers,
        notify_interval=notify_interval,
        approve_jobs=approve_jobs,
        approve_peers=approve_peers,
        approved_domains=parsed_approved_domains,
        approve_interval=approve_interval,
        credentials_path=credentials_path,
        gmail_token_path=gmail_token,
        drive_token_path=drive_token,
    )

    run_init_flow(config=config)


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
def setup():
    """Check environment and show setup status.

    Verifies that all required credentials and tokens are in place.

    Examples:

      syft-bg setup
    """
    from syft_bg.common.config import get_creds_dir
    from syft_bg.common.drive import is_colab

    creds_dir = get_creds_dir()

    click.echo()
    click.echo("SYFT-BG ENVIRONMENT CHECK")
    click.echo("=" * 50)
    click.echo()

    issues = []

    # Check credentials.json
    credentials_path = creds_dir / "credentials.json"
    click.echo("Checking credentials...")
    if credentials_path.exists():
        click.echo(f"  ✓ credentials.json found at {credentials_path}")
    else:
        click.echo(f"  ✗ credentials.json MISSING at {credentials_path}")
        issues.append(
            "Missing credentials.json:\n"
            "  1. Go to Google Cloud Console → APIs & Services → Credentials\n"
            "  2. Create OAuth 2.0 Client ID (Desktop app)\n"
            "  3. Download as credentials.json\n"
            f"  4. Place at: {credentials_path}"
        )

    # Check authentication tokens
    click.echo()
    click.echo("Checking authentication tokens...")

    gmail_token_path = creds_dir / "gmail_token.json"
    if gmail_token_path.exists():
        click.echo(f"  ✓ Gmail token: {gmail_token_path}")
    else:
        click.echo("  ✗ Gmail token: MISSING")
        issues.append(
            "Missing Gmail token:\n"
            "  Run 'syft-bg init' to complete Gmail authentication"
        )

    if not is_colab():
        drive_token_path = creds_dir / "token_do.json"
        if drive_token_path.exists():
            click.echo(f"  ✓ Drive token: {drive_token_path}")
        else:
            click.echo("  ✗ Drive token: MISSING")
            issues.append(
                "Missing Drive token:\n"
                "  Run 'syft-bg init' to complete Drive authentication"
            )
    else:
        click.echo("  ✓ Drive token: Colab (native)")

    # Check configuration
    click.echo()
    click.echo("Checking configuration...")

    config_path = creds_dir / "config.yaml"
    if config_path.exists():
        click.echo(f"  ✓ Config file: {config_path}")
        # Try to load and show email
        try:
            import yaml

            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            if "do_email" in config:
                click.echo(f"  ✓ Email: {config['do_email']}")
            if "syftbox_root" in config:
                click.echo(f"  ✓ SyftBox root: {config['syftbox_root']}")
        except Exception:
            pass
    else:
        click.echo("  ✗ Config file: MISSING")
        issues.append(
            "Missing config file:\n  Run 'syft-bg init' to create configuration"
        )

    # Summary
    click.echo()
    click.echo("-" * 50)

    if issues:
        click.echo(f"⚠️  {len(issues)} issue(s) found")
        click.echo()
        for issue in issues:
            click.echo(issue)
            click.echo()
    else:
        click.echo("✅ Environment ready! Run 'syft-bg start' to begin.")

    click.echo()


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

    Prefer using 'syft-bg set-script' which hashes and updates config
    in one step. This command is useful for inspecting hashes directly.

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


@main.command("set-script")
@click.argument("scripts", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "--peers",
    "-p",
    multiple=True,
    help="Peer email(s) to restrict to. Can be specified multiple times.",
)
@click.option(
    "--name",
    "-n",
    default=None,
    help="Name for the auto-approval object. Auto-generated if not provided.",
)
@click.option(
    "--file-names",
    "-f",
    multiple=True,
    help="Non-.py filenames to allow (e.g. params.json).",
)
@click.option(
    "--replace",
    is_flag=True,
    help="Replace existing object with this name instead of updating.",
)
def set_script(
    scripts: tuple[str, ...],
    peers: tuple[str, ...],
    name: str | None,
    file_names: tuple[str, ...],
    replace: bool,
):
    """Create or update an auto-approval object.

    Accepts multiple .py files or directories. Directories are expanded
    to all .py files within them. Scripts are copied to the managed
    auto-approvals directory and hashed.

    Examples:

      syft-bg set-script main.py -p alice@uni.edu -p bob@co.com

      syft-bg set-script main.py utils.py -n my_analysis

      syft-bg set-script ./src/ -p alice@uni.edu -f params.json
    """
    import shutil
    from pathlib import Path

    from syft_bg.approve.config import AutoApproveConfig, AutoApprovalObj, FileEntry
    from syft_bg.common.config import get_default_paths

    # Resolve all .py files from arguments (files and directories)
    py_files: list[Path] = []
    for s in scripts:
        p = Path(s)
        if p.is_dir():
            found = sorted(p.rglob("*.py"))
            if not found:
                click.echo(f"Warning: no .py files found in {p}", err=True)
            py_files.extend(found)
        elif p.suffix != ".py":
            click.echo(f"Error: {p.name} is not a .py file", err=True)
            raise SystemExit(1)
        else:
            py_files.append(p)

    if not py_files:
        click.echo("Error: no .py files to process", err=True)
        raise SystemExit(1)

    # Auto-generate name if not provided
    if name is None:
        name = py_files[0].stem if len(py_files) == 1 else "auto_approval"
        # Ensure unique name
        config = AutoApproveConfig.load()
        base_name = name
        counter = 1
        while name in config.auto_approvals.objects and not replace:
            name = f"{base_name}_{counter}"
            counter += 1
    else:
        config = AutoApproveConfig.load()

    # Copy scripts to managed directory and hash
    paths = get_default_paths()
    obj_dir = paths.auto_approvals_dir / name
    obj_dir.mkdir(parents=True, exist_ok=True)

    script_entries: list[FileEntry] = []
    for file_path in py_files:
        dest = obj_dir / file_path.name
        shutil.copy2(file_path, dest)
        content = dest.read_text(encoding="utf-8")
        file_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        script_entries.append(
            FileEntry(relative_path=file_path.name, path=str(dest), hash=file_hash)
        )

    obj = AutoApprovalObj(
        file_contents=script_entries,
        file_names=list(file_names),
        peers=list(peers),
    )

    if not replace and name in config.auto_approvals.objects:
        # Additive: merge file_contents, peers, file_names
        existing = config.auto_approvals.objects[name]
        existing_by_name = {s.relative_path: s for s in existing.file_contents}
        for entry in script_entries:
            existing_by_name[entry.relative_path] = entry
        existing.file_contents = list(existing_by_name.values())
        existing.peers = list(set(existing.peers + list(peers)))
        existing.file_names = list(set(existing.file_names + list(file_names)))
    else:
        config.auto_approvals.objects[name] = obj

    config.save()

    click.echo(f"Auto-approval object: {name}")
    for entry in script_entries:
        click.echo(f"  {entry.relative_path}  {entry.hash}")
    if peers:
        click.echo(f"Peers: {', '.join(peers)}")
    else:
        click.echo("Peers: (any)")
    if file_names:
        click.echo(f"Allowed files: {', '.join(file_names)}")
    click.echo()
    click.echo("Config updated.")

    # Check if services are running and suggest restart
    manager = ServiceManager()
    approve_svc = manager.get_service("approve")
    approve_status = approve_svc.get_status() if approve_svc else None
    if approve_status and approve_status.status == ServiceStatus.RUNNING:
        click.echo()
        if click.confirm("Approve service is running. Restart to apply changes?"):
            success, msg = manager.restart_service("approve")
            if success:
                click.echo(f"Restarted: {msg}")
            else:
                click.echo(f"Restart failed: {msg}", err=True)


@main.command("remove-script")
@click.argument("files", nargs=-1, required=True)
@click.option(
    "--name",
    "-n",
    required=True,
    help="Name of the auto-approval object to remove scripts from.",
)
def remove_script(files: tuple[str, ...], name: str):
    """Remove scripts from an auto-approval object.

    Examples:

      syft-bg remove-script utils.py -n my_analysis

      syft-bg remove-script main.py utils.py -n my_analysis
    """
    from syft_bg.approve.config import AutoApproveConfig

    config = AutoApproveConfig.load()

    if name not in config.auto_approvals.objects:
        click.echo(f"Auto-approval object '{name}' not found in config.", err=True)
        raise SystemExit(1)

    obj = config.auto_approvals.objects[name]
    before = len(obj.file_contents)
    obj.file_contents = [s for s in obj.file_contents if s.relative_path not in files]
    removed = before - len(obj.file_contents)

    config.save()
    click.echo(f"Removed {removed} script(s) from '{name}'.")


@main.command("remove-peer")
@click.argument("peer")
@click.option(
    "--name",
    "-n",
    default=None,
    help="Remove peer from a specific object only. If not given, removes from all.",
)
def remove_peer(peer: str, name: str | None):
    """Remove a peer from auto-approval objects.

    Examples:

      syft-bg remove-peer alice@uni.edu

      syft-bg remove-peer alice@uni.edu -n my_analysis
    """
    from syft_bg.approve.config import AutoApproveConfig

    config = AutoApproveConfig.load()
    removed_from = 0

    if name:
        if name not in config.auto_approvals.objects:
            click.echo(f"Auto-approval object '{name}' not found.", err=True)
            raise SystemExit(1)
        obj = config.auto_approvals.objects[name]
        if peer in obj.peers:
            obj.peers.remove(peer)
            removed_from = 1
    else:
        for obj in config.auto_approvals.objects.values():
            if peer in obj.peers:
                obj.peers.remove(peer)
                removed_from += 1

    if removed_from == 0:
        click.echo(f"Peer {peer} not found in any auto-approval object.", err=True)
        raise SystemExit(1)

    config.save()
    click.echo(f"Removed peer {peer} from {removed_from} object(s).")


@main.command("list-scripts")
@click.option(
    "--name",
    "-n",
    default=None,
    help="Show a specific auto-approval object only.",
)
def list_scripts(name: str | None):
    """List auto-approval objects and their scripts.

    Examples:

      syft-bg list-scripts

      syft-bg list-scripts -n my_analysis
    """
    from syft_bg.approve.config import AutoApproveConfig

    config = AutoApproveConfig.load()

    if not config.auto_approvals.objects:
        click.echo("No auto-approval objects configured.")
        return

    if name:
        if name not in config.auto_approvals.objects:
            click.echo(f"Auto-approval object '{name}' not found.", err=True)
            raise SystemExit(1)
        objects_to_show = {name: config.auto_approvals.objects[name]}
    else:
        objects_to_show = config.auto_approvals.objects

    for obj_name, obj in objects_to_show.items():
        click.echo(f"\n[{obj_name}]")
        if obj.file_contents:
            click.echo("  File contents:")
            for entry in obj.file_contents:
                click.echo(f"    {entry.relative_path:<30} {entry.hash}")
        else:
            click.echo("  File contents: (none)")
        if obj.file_names:
            click.echo(f"  Allowed files: {', '.join(obj.file_names)}")
        if obj.peers:
            click.echo(f"  Peers: {', '.join(obj.peers)}")
        else:
            click.echo("  Peers: (any)")
    click.echo()


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
