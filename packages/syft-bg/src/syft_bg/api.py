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


def _credentials_setup_steps(creds_path: Path, colab: bool) -> str:
    """Return step-by-step instructions for setting up credentials.json."""
    console_url = "https://console.cloud.google.com/apis/credentials"
    if colab:
        save_step = (
            f"  5. Upload the downloaded JSON file to Google Drive at: {creds_path}"
        )
    else:
        save_step = f"  5. Save the downloaded JSON file to: {creds_path}"

    return (
        f"  1. Open Google Cloud Console: {console_url}\n"
        "  2. Create a project (or select an existing one)\n"
        "  3. Click 'Create Credentials' > 'OAuth client ID'\n"
        "     - If prompted, configure the consent screen first\n"
        "       (External type, add your email as a test user)\n"
        "  4. Select 'Desktop app' as application type, then click 'Create'\n"
        f"{save_step}"
    )


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
    colab = is_colab()

    # Check credentials.json
    creds_path = (
        Path(credentials_path) if credentials_path else creds_dir / "credentials.json"
    )
    if not creds_path.exists():
        steps = _credentials_setup_steps(creds_path, colab)
        issues.append(f"credentials.json not found at {creds_path}\n{steps}")

    # Check Gmail token
    gmail_path = (
        Path(gmail_token_path) if gmail_token_path else creds_dir / "gmail_token.json"
    )
    if not gmail_path.exists():
        if creds_path.exists():
            issues.append(
                f"Gmail token not found at {gmail_path}\n"
                "  Run syft_bg.authenticate() to set it up interactively"
            )
        else:
            issues.append(
                f"Gmail token not found at {gmail_path}\n"
                "  Set up credentials.json first, then run syft_bg.authenticate()"
            )

    # Check Drive token (not needed on Colab — uses native auth)
    if not colab:
        drive_path = (
            Path(drive_token_path) if drive_token_path else creds_dir / "token_do.json"
        )
        if not drive_path.exists():
            if creds_path.exists():
                issues.append(
                    f"Drive token not found at {drive_path}\n"
                    "  Run syft_bg.authenticate() to set it up interactively"
                )
            else:
                issues.append(
                    f"Drive token not found at {drive_path}\n"
                    "  Set up credentials.json first, then run syft_bg.authenticate()"
                )

    return issues


@dataclass
class AuthResult:
    """Result of authenticate() call."""

    success: bool
    gmail_ok: bool = False
    drive_ok: bool = False
    error: str | None = None

    def __repr__(self) -> str:
        lines = []
        if self.success:
            lines.append("AuthResult: OK")
        else:
            lines.append("AuthResult: FAILED")
            if self.error:
                lines.append(f"  error: {self.error}")
        lines.append(f"  gmail: {'ready' if self.gmail_ok else 'missing'}")
        lines.append(f"  drive: {'ready' if self.drive_ok else 'missing'}")
        return "\n".join(lines)


def authenticate(
    credentials_path: str | Path | None = None,
) -> AuthResult:
    """Set up Gmail and Drive authentication interactively.

    Guides you through the OAuth flow step by step.
    Works in Colab, Jupyter, and terminal environments.

    Args:
        credentials_path: Path to credentials.json. Defaults to ~/.syft-creds/credentials.json

    Returns:
        AuthResult with status of each token.

    Example:
        >>> import syft_bg
        >>> syft_bg.authenticate()
    """
    creds_dir = get_creds_dir()
    colab = is_colab()

    creds_path = (
        Path(credentials_path).expanduser()
        if credentials_path
        else creds_dir / "credentials.json"
    )

    if not creds_path.exists():
        steps = _credentials_setup_steps(creds_path, colab)
        msg = (
            f"credentials.json not found at {creds_path}\n{steps}\n"
            "  Then run syft_bg.authenticate() again"
        )
        return AuthResult(success=False, error=msg)

    gmail_token_path = creds_dir / "gmail_token.json"
    drive_token_path = creds_dir / "token_do.json"
    gmail_ok = gmail_token_path.exists()
    drive_ok = drive_token_path.exists() or colab

    # --- Gmail token ---
    if not gmail_ok:
        print("Setting up Gmail authentication...")
        print("This is needed for email notifications.\n")
        try:
            from syft_bg.notify.gmail import GmailAuth

            auth = GmailAuth()
            credentials = auth.setup_auth(creds_path)
            gmail_token_path.parent.mkdir(parents=True, exist_ok=True)
            gmail_token_path.write_text(credentials.to_json())
            gmail_ok = True
            print(f"Gmail token saved to {gmail_token_path}\n")
        except Exception as e:
            print(f"Gmail setup failed: {e}\n")
    else:
        print(f"Gmail token already exists at {gmail_token_path}")

    # --- Drive token ---
    if colab:
        print("Drive authentication: handled natively by Colab")
        drive_ok = True
    elif not drive_ok:
        print("\nSetting up Google Drive authentication...")
        print("This is needed for monitoring jobs and peers.\n")
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            from syft_bg.common.drive import DRIVE_SCOPES

            flow = InstalledAppFlow.from_client_secrets_file(
                str(creds_path), DRIVE_SCOPES
            )
            flow.redirect_uri = "http://localhost:1"
            auth_url, _ = flow.authorization_url(
                prompt="consent", access_type="offline"
            )

            print("Visit this URL to authorize Google Drive access:\n")
            print(f"  {auth_url}\n")
            print("After authorizing, you'll see a page that won't load.")
            print("Copy the 'code' value from the URL in your browser's address bar.")
            print("(The URL looks like: http://localhost:1/?code=XXXXX&scope=...)\n")

            code = input("Paste the authorization code here: ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials

            drive_token_path.parent.mkdir(parents=True, exist_ok=True)
            drive_token_path.write_text(creds.to_json())
            drive_ok = True
            print(f"\nDrive token saved to {drive_token_path}")
        except Exception as e:
            print(f"Drive setup failed: {e}")
    else:
        print(f"Drive token already exists at {drive_token_path}")

    return AuthResult(
        success=gmail_ok and drive_ok,
        gmail_ok=gmail_ok,
        drive_ok=drive_ok,
    )


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


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@dataclass
class StatusResult:
    """Status of syft-bg services and configuration."""

    email: str | None = None
    syftbox_root: str | None = None
    services: dict[str, str] = field(default_factory=dict)
    email_configured: bool = False
    auto_approvals: dict[str, dict] = field(default_factory=dict)
    approved_domains: list[str] = field(default_factory=list)
    is_colab: bool = False

    def __repr__(self) -> str:
        lines = ["syft-bg status"]
        lines.append("=" * 40)

        # User / environment
        lines.append(f"  email:       {self.email or 'not configured'}")
        lines.append(f"  syftbox:     {self.syftbox_root or 'not configured'}")
        lines.append(f"  environment: {'Colab' if self.is_colab else 'local'}")
        lines.append(
            f"  gmail:       {'ready' if self.email_configured else 'not set up'}"
        )

        # Services
        lines.append("")
        lines.append("services")
        lines.append("-" * 40)
        for name, svc_status in self.services.items():
            lines.append(f"  {name:<12} {svc_status}")

        # Auto-approval objects
        if self.auto_approvals:
            lines.append("")
            lines.append("auto-approval objects")
            lines.append("-" * 40)
            for obj_name, obj_data in self.auto_approvals.items():
                lines.append(f"  [{obj_name}]")
                for script in obj_data.get("scripts", []):
                    lines.append(f"    script: {script}")
                for fname in obj_data.get("file_names", []):
                    lines.append(f"    file:   {fname}")
                peers = obj_data.get("peers", [])
                if peers:
                    lines.append(f"    peers:  {', '.join(peers)}")
                else:
                    lines.append("    peers:  (any)")

        # Approved domains
        if self.approved_domains:
            lines.append("")
            lines.append("auto-approved domains")
            lines.append("-" * 40)
            for domain in self.approved_domains:
                lines.append(f"  {domain}")

        return "\n".join(lines)


def status() -> StatusResult:
    """Get the current status of syft-bg services and configuration.

    Returns:
        StatusResult with service states, user info, and approval config.

    Example:
        >>> import syft_bg
        >>> syft_bg.status
        syft-bg status
        ========================================
          email:       user@example.com
          syftbox:     ~/SyftBox
          environment: local
          gmail:       ready
        ...
    """
    from syft_bg.common.config import get_default_paths, load_yaml
    from syft_bg.services import ServiceManager
    from syft_bg.services.base import ServiceStatus

    creds_dir = get_creds_dir()
    paths = get_default_paths()
    colab = is_colab()

    # Load config
    config = load_yaml(paths.config)

    # Service status
    manager = ServiceManager()
    services = {}
    for name, info in manager.get_all_status().items():
        if info.status == ServiceStatus.RUNNING:
            services[name] = f"running (PID {info.pid})"
        else:
            services[name] = "stopped"

    # Gmail token
    gmail_token_path = creds_dir / "gmail_token.json"
    email_configured = gmail_token_path.exists()

    # Approval config
    auto_approvals: dict[str, dict] = {}
    approved_domains: list[str] = []
    approve_section = config.get("approve", {})
    aa_section = approve_section.get("auto_approvals", {})
    peers_section = approve_section.get("peers", {})

    for obj_name, obj_data in aa_section.get("objects", {}).items():
        auto_approvals[obj_name] = {
            "scripts": [s.get("name", "?") for s in obj_data.get("scripts", [])],
            "file_names": obj_data.get("file_names", []),
            "peers": obj_data.get("peers", []),
        }

    approved_domains = peers_section.get("approved_domains", [])

    return StatusResult(
        email=config.get("do_email"),
        syftbox_root=config.get("syftbox_root"),
        services=services,
        email_configured=email_configured,
        auto_approvals=auto_approvals,
        approved_domains=approved_domains,
        is_colab=colab,
    )
