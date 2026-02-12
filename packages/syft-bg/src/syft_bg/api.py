"""Pythonic API for syft-bg initialization and configuration."""

from dataclasses import dataclass
from pathlib import Path

from syft_bg.cli.init import InitConfig, run_init_flow
from syft_bg.common.config import get_creds_dir


@dataclass
class InitResult:
    """Result of init() call."""

    success: bool
    config_path: Path | None = None
    error: str | None = None


def init(
    email: str,
    syftbox_root: str | Path | None = None,
    *,
    # Notification settings
    notify_jobs: bool = True,
    notify_peers: bool = True,
    notify_interval: int = 30,
    # Job approval settings
    approve_jobs: bool = True,
    jobs_peers_only: bool = True,
    required_filenames: list[str] | None = None,
    allowed_users: list[str] | None = None,
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
        notify_jobs: Enable email notifications for new jobs
        notify_peers: Enable email notifications for peer requests
        notify_interval: Notification check interval in seconds
        approve_jobs: Enable automatic job approval
        jobs_peers_only: Only approve jobs from approved peers
        required_filenames: Required filenames for job validation
        allowed_users: Allowed users (empty = all approved peers)
        approve_peers: Enable automatic peer approval
        approved_domains: Approved domains for peer auto-approval
        approve_interval: Approval check interval in seconds
        credentials_path: Path to credentials.json for OAuth
        gmail_token_path: Path to pre-existing Gmail token
        drive_token_path: Path to pre-existing Drive token
        skip_oauth: Skip OAuth setup (tokens must exist)
        verbose: Print progress messages

    Returns:
        InitResult with success status and config path

    Example:
        >>> import syft_bg
        >>> result = syft_bg.init(
        ...     email="user@example.com",
        ...     syftbox_root="~/SyftBox",
        ...     notify_jobs=True,
        ...     approve_jobs=True,
        ...     skip_oauth=True,
        ... )
        >>> if result.success:
        ...     print(f"Config saved to {result.config_path}")
    """
    # Set default syftbox_root if not provided
    if syftbox_root is None:
        syftbox_root = str(Path.home() / f"SyftBox_{email}")
    else:
        syftbox_root = str(syftbox_root)

    # Set default values for lists
    if required_filenames is None:
        required_filenames = ["main.py", "params.json"]
    if approved_domains is None:
        approved_domains = ["openmined.org"]
    if allowed_users is None:
        allowed_users = []

    try:
        creds_dir = get_creds_dir()
        config_path = creds_dir / "config.yaml"

        # Build InitConfig
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
            jobs_peers_only=jobs_peers_only,
            required_filenames=required_filenames,
            allowed_users=allowed_users,
            approve_peers=approve_peers,
            approved_domains=approved_domains,
            approve_interval=approve_interval,
            credentials_path=str(credentials_path) if credentials_path else None,
            gmail_token_path=str(gmail_token_path) if gmail_token_path else None,
            drive_token_path=str(drive_token_path) if drive_token_path else None,
        )

        # Run init flow
        success = run_init_flow(config=config)

        if success:
            return InitResult(success=True, config_path=config_path)
        else:
            return InitResult(success=False, error="Init flow returned False")

    except Exception as e:
        return InitResult(success=False, error=str(e))
