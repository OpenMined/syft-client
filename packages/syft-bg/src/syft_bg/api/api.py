"""Pythonic API for syft-bg initialization and configuration."""

import shutil
from pathlib import Path

from syft_bg.api.results import AutoApproveResult, StatusResult
from syft_bg.api.utils import (
    copy_and_hash_files,
    generate_unique_name,
    get_job_user_files,
    move_token_to_syftbg_dir,
    resolve_auto_approve_file_args,
    resolve_content_files,
    restart_approve_service,
    validate_auto_approve_job_inputs,
)
from syft_bg.approve.config import AutoApproveConfig, AutoApprovalObj
from syft_bg.common.config import get_syftbg_dir, get_default_paths
from syft_bg.common.drive import is_colab
from syft_bg.common.syft_bg_config import SyftBgConfig
from syft_bg.services import ServiceManager


# perhaps add this later again
# def authenticate(
#     credentials_path: str | Path | None = None,
# ) -> AuthResult:
#     """Set up Gmail and Drive authentication interactively.

#     Guides you through the OAuth flow step by step.
#     Works in Colab, Jupyter, and terminal environments.

#     Args:
#         credentials_path: Path to credentials.json. Defaults to ~/.syft-bg/credentials.json

#     Returns:
#         AuthResult with status of each token.

#     Example:
#         >>> import syft_bg
#         >>> syft_bg.authenticate()
#     """
#     creds_dir = get_syftbg_dir()
#     colab = is_colab()

#     creds_path = (
#         Path(credentials_path).expanduser()
#         if credentials_path
#         else creds_dir / "credentials.json"
#     )

#     if not creds_path.exists():
#         steps = credentials_setup_steps(creds_path, colab)
#         msg = (
#             f"credentials.json not found at {creds_path}\n{steps}\n"
#             "  Then run syft_bg.authenticate() again"
#         )
#         return AuthResult(success=False, error=msg)

#     gmail_out_token_path = creds_dir / "gmail_token.json"
#     drive_out_token_path = creds_dir / "drive_token.json"
#     gmail_ok = gmail_out_token_path.exists()
#     drive_ok = drive_out_token_path.exists() or colab

#     # --- Gmail token ---
#     if not gmail_ok:
#         authenticate_and_save(gmail_out_token_path, creds_path)
#     else:
#         print(f"Gmail token already exists at {gmail_out_token_path}")

#     # --- Drive token ---
#     if colab:
#         print("Drive authentication: handled natively by Colab")
#         drive_ok = True
#     elif not drive_ok:
#         authenticate_drive(drive_out_token_path, creds_path)
#     else:
#         print(f"Drive token already exists at {drive_out_token_path}")

#     # Save GCP project ID from credentials.json into config so it's
#     # available at runtime without needing the credentials file.
#     save_gcp_project_id(creds_path)

#     return AuthResult(
#         success=gmail_ok and drive_ok,
#         gmail_ok=gmail_ok,
#         drive_ok=drive_ok,
#     )


def init(
    do_email: str,
    syftbox_root: str | Path | None = None,
    token_path: str | Path | None = None,
) -> None:
    if token_path is not None:
        token_path = Path(token_path)
        move_token_to_syftbg_dir(token_path)

    config = SyftBgConfig(
        do_email=do_email,
        syftbox_root=syftbox_root,
        token_path=token_path,
        drive_token_path=token_path,
    )
    config.save()
    print(f"Config saved to {get_default_paths().config}")


def ensure_running(
    services: dict[str, dict] | list[str], restart: bool = False
) -> None:
    # store new settings
    try:
        config = SyftBgConfig.from_path()
    except FileNotFoundError:
        print("No config file found, run init first")
        return

    if isinstance(services, list):
        services = {name: {} for name in services}
    manager = ServiceManager()

    # store new settings
    for name, service_config in services.items():
        service = manager.get_service(name)
        if not service:
            raise ValueError(f"Unknown service: {name}")
        config.set_service_config(name, service_config)

    config.save()

    # make sure services are running
    for name, service_config in services.items():
        service = manager.get_service(name)
        if service.is_running() and not restart:
            print(
                f"{name} is already running, skipping. If you want to restart it, set restart=True."
            )
            continue
        elif service.is_running() and restart:
            manager.restart_service(name)
        else:
            manager.start_service(name)
            print(f"{name} started")


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
    manager = ServiceManager()
    if service:
        return {service: manager.restart_service(service)}
    results = {}
    for name in manager.list_services():
        results[name] = manager.restart_service(name)
    return results


def reset() -> None:
    """Stop all services and clear all state, logs, and PID files.

    This gives you a clean slate without removing tokens or config.
    """
    manager = ServiceManager()
    manager.stop_all()

    syftbg_dir = get_syftbg_dir()
    shutil.rmtree(syftbg_dir, ignore_errors=True)
    print("Reset complete: stopped services, cleared state, logs, and PID files.")


def logs(service: str, n: int = 50) -> list[str]:
    """Get recent log lines for a service.

    Args:
        service: Service name ("notify" or "approve").
        n: Number of lines to return.

    Returns:
        List of log lines.
    """
    manager = ServiceManager()
    return manager.get_logs(service, n)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


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
    from syft_bg.common.config import load_yaml
    from syft_bg.services.base import ServiceStatus

    creds_dir = get_syftbg_dir()
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
            "file_paths": obj_data.get("file_paths", []),
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


def auto_approve(
    contents: list[str | Path],
    file_paths: list[str] | None = None,
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
        file_paths: Relative paths to allow by name only (e.g. ["params.json"]).
        peers: Peer emails to restrict to. If None or empty, any peer matches.
        name: Name for the auto-approval object. Auto-generated if not provided.
        base_dir: Base directory to resolve relative paths in contents against.
                  When set, FileEntry.relative_path stores the relative path.

    Returns:
        AutoApproveResult with the created object details.
    """
    if file_paths is None:
        file_paths = []
    if peers is None:
        peers = []

    content_files, error = resolve_content_files(contents, base_dir)
    if error:
        return AutoApproveResult(success=False, error=error)

    if not content_files and not file_paths:
        return AutoApproveResult(success=False, error="No files to process")

    config = AutoApproveConfig.load()
    name = generate_unique_name(name, content_files, config)

    file_entries = copy_and_hash_files(content_files, name)

    obj = AutoApprovalObj(
        file_contents=file_entries,
        file_paths=file_paths,
        peers=peers,
    )
    config.auto_approvals.objects[name] = obj
    config.save()

    restart_approve_service()

    return AutoApproveResult(
        success=True,
        name=name,
        file_contents=[e.relative_path for e in file_entries],
        file_paths=file_paths,
        peers=peers,
    )


def auto_approve_job(
    job,
    contents: list[str] | None = None,
    file_paths: list[str] | None = None,
    peers: list[str] | None = None,
    name: str | None = None,
) -> AutoApproveResult:
    """Create an auto-approval config from an existing job.

    Extracts files from the job and routes them to auto_approve() based on
    the contents and file_paths parameters.

    Args:
        job: JobInfo object to use as template.
        contents: Filenames from the job to match by name AND content.
                  If None and file_paths is None, all files are content-matched.
                  If None and file_paths is set, all other files are content-matched.
        file_paths: Filenames from the job to match by name only.
        peers: Peer emails to restrict to. If None, defaults to the job's submitter.
        name: Name for the auto-approval object. Defaults to job name.

    Returns:
        AutoApproveResult with the created object details.
    """
    if peers is None:
        peers = [job.submitted_by]

    user_files = get_job_user_files(job)

    error = validate_auto_approve_job_inputs(user_files, contents, file_paths)
    if error:
        return AutoApproveResult(success=False, error=error)

    content_rel_paths, name_only = resolve_auto_approve_file_args(
        user_files, contents, file_paths
    )

    if name is None:
        name = job.name

    return auto_approve(
        contents=content_rel_paths,
        file_paths=name_only,
        peers=peers,
        name=name,
        base_dir=job.code_dir,
    )
