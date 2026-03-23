"""Pythonic API for syft-bg initialization and configuration."""

from dataclasses import dataclass, field
from pathlib import Path

from syft_bg.cli.init import InitConfig, run_init_flow
from syft_bg.common.config import get_creds_dir
from syft_bg.common.drive import is_colab


@dataclass
class InitResult:
    """Result of init() call."""

    success: bool
    config_path: Path | None = None
    error: str | None = None
    services: dict[str, tuple[bool, str]] | None = None
    issues: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        lines = []
        if self.success:
            lines.append("InitResult: OK")
            if self.config_path:
                lines.append(f"  config: {self.config_path}")
            if self.services:
                for name, (ok, msg) in self.services.items():
                    status = "started" if ok else "failed"
                    lines.append(f"  {name}: {status} — {msg}")
        else:
            lines.append("InitResult: FAILED")
            if self.error:
                lines.append(f"  error: {self.error}")
        if self.issues:
            lines.append("  issues:")
            for issue in self.issues:
                # Indent continuation lines of multi-line issues
                indented = issue.replace("\n", "\n      ")
                lines.append(f"    - {indented}")
        return "\n".join(lines)


def _check_prerequisites(
    credentials_path: Path | None = None,
    gmail_token_path: Path | None = None,
    drive_token_path: Path | None = None,
) -> list[str]:
    """Check that all required credentials and tokens are in place.

    Returns a list of issues. Empty list means all prerequisites are met.
    """
    creds_dir = get_creds_dir()
    issues = []

    auth_docs = "https://github.com/OpenMined/syft-client/blob/main/docs/auth.md"

    # Check credentials.json
    creds_path = (
        Path(credentials_path) if credentials_path else creds_dir / "credentials.json"
    )
    if not creds_path.exists():
        issues.append(
            f"credentials.json not found at {creds_path}\n"
            f"  Follow the setup guide: {auth_docs}\n"
            f"  Then place credentials.json at: {creds_path}"
        )

    # Check Gmail token
    gmail_path = (
        Path(gmail_token_path) if gmail_token_path else creds_dir / "gmail_token.json"
    )
    if not gmail_path.exists():
        issues.append(
            f"Gmail token not found at {gmail_path}\n"
            f"  Generate it: python scripts/create_token.py --credentials {creds_path} --output {gmail_path}\n"
            f"  Or pass an existing token: syft_bg.init(..., gmail_token_path='path/to/token.json')"
        )

    # Check Drive token (not needed on Colab)
    if not is_colab():
        drive_path = (
            Path(drive_token_path) if drive_token_path else creds_dir / "token_do.json"
        )
        if not drive_path.exists():
            issues.append(
                f"Drive token not found at {drive_path}\n"
                f"  Generate it: python scripts/create_token.py --credentials {creds_path} --output {drive_path}\n"
                f"  Or pass an existing token: syft_bg.init(..., drive_token_path='path/to/token.json')"
            )

    return issues


def init(
    email: str,
    syftbox_root: str | Path | None = None,
    *,
    start: bool = False,
    # Notification settings
    notify_jobs: bool = True,
    notify_peers: bool = True,
    notify_interval: int = 30,
    # Job approval settings
    approve_jobs: bool = True,
    # Peer approval settings
    approve_peers: bool = False,
    approved_domains: list[str] | None = None,
    approve_interval: int = 5,
    # OAuth settings
    credentials_path: str | Path | None = None,
    gmail_token_path: str | Path | None = None,
    drive_token_path: str | Path | None = None,
    skip_oauth: bool = False,
    # Output control
    verbose: bool = False,
) -> InitResult:
    """Initialize syft-bg services programmatically.

    This function provides a Pythonic interface for configuring syft-bg,
    suitable for use in Jupyter notebooks or scripts.

    Args:
        email: Data Owner email address (required)
        syftbox_root: SyftBox root directory. Defaults to ~/SyftBox_{email}
        start: Start services after initialization
        notify_jobs: Enable email notifications for new jobs
        notify_peers: Enable email notifications for peer requests
        notify_interval: Notification check interval in seconds
        approve_jobs: Enable automatic job approval
        approve_peers: Enable automatic peer approval
        approved_domains: Approved domains for peer auto-approval
        approve_interval: Approval check interval in seconds
        credentials_path: Path to credentials.json for OAuth
        gmail_token_path: Path to pre-existing Gmail token
        drive_token_path: Path to pre-existing Drive token
        skip_oauth: Skip OAuth setup (tokens must exist)
        verbose: Print progress messages

    Returns:
        InitResult with success status, config path, and any issues

    Example:
        >>> import syft_bg
        >>> result = syft_bg.init(email="user@example.com", start=True)
        >>> result
        InitResult: OK
          config: ~/.syft-creds/config.yaml
          notify: started — notify started (PID 12345)
          approve: started — approve started (PID 12346)
    """
    # Set default syftbox_root if not provided
    if syftbox_root is None:
        syftbox_root = str(Path.home() / f"SyftBox_{email}")
    else:
        syftbox_root = str(syftbox_root)

    if approved_domains is None:
        approved_domains = ["openmined.org"]

    try:
        creds_dir = get_creds_dir()
        config_path = creds_dir / "config.yaml"

        # Check prerequisites before doing anything
        if start:
            issues = _check_prerequisites(
                credentials_path=credentials_path,
                gmail_token_path=gmail_token_path,
                drive_token_path=drive_token_path,
            )
            if issues:
                return InitResult(
                    success=False,
                    error="Prerequisites missing — cannot start services",
                    issues=issues,
                )

        config = InitConfig(
            email=email,
            syftbox_root=syftbox_root,
            yes=True,  # API always overwrites
            quiet=not verbose,
            skip_oauth=skip_oauth,
            notify_jobs=notify_jobs,
            notify_peers=notify_peers,
            notify_interval=notify_interval,
            approve_jobs=approve_jobs,
            approve_peers=approve_peers,
            approved_domains=approved_domains,
            approve_interval=approve_interval,
            credentials_path=str(credentials_path) if credentials_path else None,
            gmail_token_path=str(gmail_token_path) if gmail_token_path else None,
            drive_token_path=str(drive_token_path) if drive_token_path else None,
        )

        success = run_init_flow(config=config)

        if not success:
            return InitResult(success=False, error="Init flow failed")

        result = InitResult(success=True, config_path=config_path)

        if start:
            from syft_bg.services import ServiceManager

            manager = ServiceManager()
            result.services = manager.start_all()

            # Check if any service failed to start
            for name, (ok, msg) in result.services.items():
                if not ok:
                    result.issues.append(f"{name}: {msg}")

            if result.issues:
                result.success = False
                result.error = "Services failed to start"

        return result

    except Exception as e:
        return InitResult(success=False, error=str(e))


# ---------------------------------------------------------------------------
# Service control
# ---------------------------------------------------------------------------


def start(service: str | None = None) -> dict[str, tuple[bool, str]]:
    """Start background services.

    Args:
        service: Name of a specific service to start (e.g. "notify", "approve").
                 If None, starts all services.

    Returns:
        Dict mapping service name to (success, message).
    """
    from syft_bg.services import ServiceManager

    manager = ServiceManager()
    if service:
        return {service: manager.start_service(service)}
    return manager.start_all()


def stop(service: str | None = None) -> dict[str, tuple[bool, str]]:
    """Stop background services.

    Args:
        service: Name of a specific service to stop.
                 If None, stops all services.

    Returns:
        Dict mapping service name to (success, message).
    """
    from syft_bg.services import ServiceManager

    manager = ServiceManager()
    if service:
        return {service: manager.stop_service(service)}
    return manager.stop_all()


def restart(service: str | None = None) -> dict[str, tuple[bool, str]]:
    """Restart background services.

    Args:
        service: Name of a specific service to restart.
                 If None, restarts all services.

    Returns:
        Dict mapping service name to (success, message).
    """
    from syft_bg.services import ServiceManager

    manager = ServiceManager()
    if service:
        return {service: manager.restart_service(service)}
    results = {}
    for name in manager.list_services():
        results[name] = manager.restart_service(name)
    return results


def logs(service: str, n: int = 50) -> list[str]:
    """Get recent log lines for a service.

    Args:
        service: Service name ("notify" or "approve").
        n: Number of lines to return.

    Returns:
        List of log lines.
    """
    from syft_bg.services import ServiceManager

    manager = ServiceManager()
    return manager.get_logs(service, n)


def ensure_running() -> dict[str, tuple[bool, str]]:
    """Ensure all services are running. Start any that have stopped.

    Useful in Colab/Jupyter notebook cells to recover from daemon crashes.

    Returns:
        Dict mapping service name to (success, message).
    """
    from syft_bg.services import ServiceManager

    manager = ServiceManager()
    results = {}
    for name in manager.list_services():
        svc = manager.get_service(name)
        if svc and svc.is_running():
            results[name] = (True, f"already running (PID {svc.get_pid()})")
        else:
            results[name] = manager.start_service(name)
    return results
