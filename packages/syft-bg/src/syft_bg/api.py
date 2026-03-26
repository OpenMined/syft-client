"""Pythonic API for syft-bg initialization and configuration."""

import hashlib
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from syft_bg.approve.config import AutoApproveConfig, AutoApprovalObj, FileEntry
from syft_bg.cli.init import InitConfig, run_init_flow
from syft_bg.common.config import get_creds_dir, get_default_paths
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
                for entry in obj_data.get("file_contents", []):
                    lines.append(f"    content: {entry}")
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
            "file_contents": [
                s.get("name", "?") for s in obj_data.get("file_contents", [])
            ],
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


# ---------------------------------------------------------------------------
# Auto-approve
# ---------------------------------------------------------------------------


@dataclass
class AutoApproveResult:
    """Result of auto_approve() call."""

    success: bool
    name: str = ""
    file_contents: list[str] = field(default_factory=list)
    file_names: list[str] = field(default_factory=list)
    peers: list[str] = field(default_factory=list)
    error: str | None = None

    def __repr__(self) -> str:
        lines = []
        if self.success:
            lines.append(f"AutoApproveResult: OK [{self.name}]")
            if self.file_contents:
                lines.append("  file_contents:")
                for s in self.file_contents:
                    lines.append(f"    - {s}")
            if self.file_names:
                lines.append(f"  file_names: {', '.join(self.file_names)}")
            if self.peers:
                lines.append(f"  peers: {', '.join(self.peers)}")
            else:
                lines.append("  peers: (any)")
        else:
            lines.append("AutoApproveResult: FAILED")
            if self.error:
                lines.append(f"  error: {self.error}")
        return "\n".join(lines)


def _generate_unique_name(
    name: str | None,
    content_files: list[tuple[str, Path]],
    config: AutoApproveConfig,
) -> str:
    """Generate a unique name for an auto-approval object."""
    if name is None:
        if content_files:
            first_rel = content_files[0][0]
            name = Path(first_rel).stem if len(content_files) == 1 else "auto_approval"
        else:
            name = "auto_approval"

    if name in config.auto_approvals.objects:
        base_name = name
        counter = 1
        while f"{base_name}_{counter}" in config.auto_approvals.objects:
            counter += 1
        name = f"{base_name}_{counter}"

    return name


def _resolve_content_files(
    contents: list[str | Path], base_dir: Path | None
) -> tuple[list[tuple[str, Path]], str | None]:
    """Resolve content paths to (relative_path, absolute_path) pairs.

    Returns (content_files, error). error is None on success.
    """
    content_files: list[tuple[str, Path]] = []
    for item in contents:
        if base_dir is not None:
            rel = str(item)
            abs_path = base_dir / rel
            if not abs_path.exists():
                return [], f"File not found: {abs_path}"
            content_files.append((rel, abs_path))
        else:
            p = Path(item).expanduser()
            if p.is_dir():
                found = sorted(f for f in p.rglob("*") if f.is_file())
                if not found:
                    return [], f"No files found in {p}"
                for f in found:
                    content_files.append((str(f.relative_to(p)), f))
            elif not p.exists():
                return [], f"File not found: {p}"
            else:
                content_files.append((p.name, p))
    return content_files, None


def _copy_and_hash_files(
    content_files: list[tuple[str, Path]], name: str
) -> list[FileEntry]:
    """Copy files to the managed auto-approvals directory and compute hashes."""
    obj_dir = get_default_paths().auto_approvals_dir / name
    obj_dir.mkdir(parents=True, exist_ok=True)

    entries: list[FileEntry] = []
    for rel_path, abs_path in content_files:
        dest = obj_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(abs_path, dest)
        content = dest.read_text(encoding="utf-8")
        file_hash = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
        entries.append(
            FileEntry(relative_path=rel_path, path=str(dest), hash=file_hash)
        )
    return entries


def _restart_approve_service() -> None:
    """Restart the approve service if it is currently running."""
    try:
        from syft_bg.services import ServiceManager
        from syft_bg.services.base import ServiceStatus

        manager = ServiceManager()
        approve_svc = manager.get_service("approve")
        if approve_svc:
            svc_status = approve_svc.get_status()
            if svc_status and svc_status.status == ServiceStatus.RUNNING:
                manager.restart_service("approve")
    except Exception:
        pass


def auto_approve(
    contents: list[str | Path],
    file_names: list[str] | None = None,
    peers: list[str] | None = None,
    name: str | None = None,
    base_dir: Path | None = None,
) -> AutoApproveResult:
    """Create an auto-approval object.

    Copies files to a managed directory, computes hashes, and saves
    the approval configuration. The approve service will use this to
    automatically approve matching jobs.

    Args:
        contents: List of file paths to approve by content. When base_dir is set,
                  these are relative paths resolved against it. Otherwise,
                  absolute paths or directories (expanded to all files within).
        file_names: Relative paths to allow by name only (e.g. ["params.json"]).
        peers: Peer emails to restrict to. If None or empty, any peer matches.
        name: Name for the auto-approval object. Auto-generated if not provided.
        base_dir: Base directory to resolve relative paths in contents against.
                  When set, FileEntry.relative_path stores the relative path.

    Returns:
        AutoApproveResult with the created object details.
    """
    if file_names is None:
        file_names = []
    if peers is None:
        peers = []

    content_files, error = _resolve_content_files(contents, base_dir)
    if error:
        return AutoApproveResult(success=False, error=error)

    if not content_files and not file_names:
        return AutoApproveResult(success=False, error="No files to process")

    config = AutoApproveConfig.load()
    name = _generate_unique_name(name, content_files, config)

    file_entries = _copy_and_hash_files(content_files, name)

    obj = AutoApprovalObj(
        file_contents=file_entries,
        file_names=file_names,
        peers=peers,
    )
    config.auto_approvals.objects[name] = obj
    config.save()

    _restart_approve_service()

    return AutoApproveResult(
        success=True,
        name=name,
        file_contents=[e.relative_path for e in file_entries],
        file_names=file_names,
        peers=peers,
    )


PERMISSION_FILE_NAME = "syft.pub.yaml"


def _resolve_auto_approve_file_args(
    user_files: dict[str, Path],
    contents: list[str] | None,
    file_names: list[str] | None,
) -> tuple[list[str], list[str]]:
    """Determine which job files are content-matched vs name-only.

    Returns (content_rel_paths, name_only).
    """
    if contents is None and file_names is None:
        return list(user_files.keys()), []
    elif contents is not None and file_names is None:
        return list(contents), []
    elif contents is None and file_names is not None:
        name_only = list(file_names)
        content_rel_paths = [rel for rel in user_files if rel not in set(file_names)]
        return content_rel_paths, name_only
    else:
        return list(contents), list(file_names)  # type: ignore[arg-type]


def _validate_auto_approve_job_inputs(
    user_files: dict[str, Path],
    contents: list[str] | None,
    file_names: list[str] | None,
) -> str | None:
    """Validate inputs for auto_approve_job. Returns error string or None."""
    if not user_files:
        return "No user files found in job"
    if contents is not None:
        for fname in contents:
            if fname not in user_files:
                return f"File '{fname}' not found in job"
    if file_names is not None:
        for fname in file_names:
            if fname not in user_files:
                return f"File '{fname}' not found in job"
    if contents is not None and file_names is not None:
        overlap = set(contents) & set(file_names)
        if overlap:
            return f"Overlap between contents and file_names: {overlap}"
    return None


def _get_job_user_files(job) -> dict[str, Path]:
    """Get user files from a job's code directory as {relative_path: abs_path} mapping."""
    user_files: dict[str, Path] = {}
    code_dir = job.code_dir
    if code_dir.exists():
        for f in code_dir.rglob("*"):
            if f.is_file() and f.name != PERMISSION_FILE_NAME:
                user_files[str(f.relative_to(code_dir))] = f
    return user_files


def auto_approve_job(
    job,
    contents: list[str] | None = None,
    file_names: list[str] | None = None,
    peers: list[str] | None = None,
    name: str | None = None,
) -> AutoApproveResult:
    """Create an auto-approval config from an existing job.

    Extracts files from the job and routes them to auto_approve() based on
    the contents and file_names parameters.

    Args:
        job: JobInfo object to use as template.
        contents: Filenames from the job to match by name AND content.
                  If None and file_names is None, all files are content-matched.
                  If None and file_names is set, all other files are content-matched.
        file_names: Filenames from the job to match by name only.
        peers: Peer emails to restrict to. If None, defaults to the job's submitter.
        name: Name for the auto-approval object. Defaults to job name.

    Returns:
        AutoApproveResult with the created object details.
    """
    if peers is None:
        peers = [job.submitted_by]

    user_files = _get_job_user_files(job)

    error = _validate_auto_approve_job_inputs(user_files, contents, file_names)
    if error:
        return AutoApproveResult(success=False, error=error)

    content_rel_paths, name_only = _resolve_auto_approve_file_args(
        user_files, contents, file_names
    )

    if name is None:
        name = job.name

    return auto_approve(
        contents=content_rel_paths,
        file_names=name_only,
        peers=peers,
        name=name,
        base_dir=job.code_dir,
    )
