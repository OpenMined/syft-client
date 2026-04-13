import sys
from pathlib import Path

from syft_client.gdrive_utils import (
    delete_local_syftbox,
    delete_remote_syftbox,
    read_local_version,
    write_local_version,
)
from syft_client.sync.utils.syftbox_utils import check_env
from syft_client.sync.environments.environment import Environment
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.version.version_info import VersionInfo
from syft_client.sync.utils.print_utils import print_client_connected
from syft_client.sync.utils.syftbox_utils import get_email_colab
from syft_client.sync.config.config import settings
from syft_client.version import SYFT_CLIENT_VERSION


def _detect_version_state(
    client: SyftboxManager,
) -> tuple[VersionInfo | None, VersionInfo | None]:
    """Read local and remote version info. Returns (local, remote)."""
    local_version = read_local_version(client.syftbox_folder)
    remote_version = client.read_own_version()
    return local_version, remote_version


def _has_mismatch(
    local_version: VersionInfo | None,
    remote_version: VersionInfo | None,
) -> bool:
    """Return True if either stored version differs from installed."""
    if local_version and local_version.syft_client_version != SYFT_CLIENT_VERSION:
        return True
    if remote_version and remote_version.syft_client_version != SYFT_CLIENT_VERSION:
        return True
    return False


def _print_version_status(
    local_version: VersionInfo | None,
    remote_version: VersionInfo | None,
) -> None:
    """Print a summary of the three version components."""
    local_str = local_version.syft_client_version if local_version else "(none)"
    remote_str = remote_version.syft_client_version if remote_version else "(none)"
    print("\n⚠️  Version mismatch detected.")
    print(f"  Installed client:  {SYFT_CLIENT_VERSION}")
    print(f"  Local SyftBox:     {local_str}")
    print(f"  Remote SyftBox:    {remote_str}\n")


def _prompt_mismatch(
    local_version: VersionInfo | None,
    remote_version: VersionInfo | None,
) -> str:
    """Prompt user about version mismatch. Returns choice."""
    _print_version_status(local_version, remote_version)
    print(f"  [1] Upgrade to v{SYFT_CLIENT_VERSION} (old remote data preserved)")
    print(f"  [2] Delete all state and start fresh with v{SYFT_CLIENT_VERSION}")
    print("  [3] Quit\n")
    choice = input("Choice [1/2/3]: ").strip()
    if choice not in ("1", "2", "3"):
        print(f"Invalid choice '{choice}'. Exiting.")
        sys.exit(1)
    return choice


def _get_client_token_path(client: SyftboxManager) -> Path | None:
    """Extract token_path from the client's connection."""
    connections = client.peer_manager.connection_router.connections
    if connections:
        return getattr(connections[0], "token_path", None)
    return None


def _delete_all_state(client: SyftboxManager) -> None:
    """Delete local + remote SyftBox state and reset caches."""
    token_path = _get_client_token_path(client)
    delete_local_syftbox(
        email=client.email,
        local_syftbox_path=client.syftbox_folder,
        verbose=True,
    )
    delete_remote_syftbox(
        email=client.email,
        token_path=token_path,
        verbose=True,
    )
    client.reset_all_connection_caches()


def _handle_mismatch(
    client: SyftboxManager,
    local_version: VersionInfo | None,
    remote_version: VersionInfo | None,
) -> None:
    """Handle version mismatch with unified prompt."""
    choice = _prompt_mismatch(local_version, remote_version)
    if choice == "1":
        print(f"Upgrading to v{SYFT_CLIENT_VERSION}...")
        delete_local_syftbox(
            email=client.email,
            local_syftbox_path=client.syftbox_folder,
            verbose=True,
        )
        client.reset_all_connection_caches()
        print("Done. Continuing login.\n")
    elif choice == "2":
        print(f"Deleting all state and starting fresh with v{SYFT_CLIENT_VERSION}...")
        _delete_all_state(client)
        print("Done. Continuing login.\n")
    else:
        print("Exiting.")
        sys.exit(0)


def _check_existing_state_version(client: SyftboxManager) -> None:
    """Check local and remote versions against installed version.

    On mismatch, prompts user to upgrade (local delete only, remote preserved
    via version subfolders) or hard-reset (delete everything).
    """
    local_version, remote_version = _detect_version_state(client)
    if not _has_mismatch(local_version, remote_version):
        return
    _handle_mismatch(client, local_version, remote_version)


def _init_client(
    client: SyftboxManager, sync: bool, load_peers: bool
) -> SyftboxManager:
    """Common post-creation initialization: version check, write version, sync, load peers."""
    _check_existing_state_version(client)

    # Write current version to both local and remote
    write_local_version(client.syftbox_folder)
    client.write_own_version()

    # Load peers early so we can restore local permissions before sync.
    # After a version upgrade that deletes local state, permission files
    # (syft.pub.yaml) are lost — this restores them for approved peers.
    client.load_peers()
    client.ensure_local_peer_permissions()

    if sync:
        client.sync()
    if load_peers:
        client.load_peers()
    print_client_connected(client)
    return client


def login(
    email: str | None = None,
    sync: bool = True,
    load_peers: bool = True,
    token_path: str | Path | None = None,
):
    return login_ds(email, sync, load_peers)


def login_ds(
    email: str | None = None,
    sync: bool = True,
    load_peers: bool = True,
    token_path: str | Path | None = None,
):
    env = check_env()

    if env == Environment.COLAB:
        if email is None:
            email = get_email_colab()
        if email is None:
            raise ValueError("Email is required for Colab login")
        client = SyftboxManager.for_colab(email=email, has_ds_role=True)
    elif env == Environment.JUPYTER:
        token_path = token_path or settings.token_path
        if not token_path:
            raise NotImplementedError(
                "Jupyter login is only supported with a token path"
            )
        if email is None:
            raise ValueError("Email is required for Jupyter login")

        client = SyftboxManager.for_jupyter(
            email=email, has_ds_role=True, token_path=token_path
        )
    else:
        raise ValueError(f"Environment {env} not supported")

    return _init_client(client, sync, load_peers)


def login_do(
    email: str | None = None,
    sync: bool = True,
    load_peers: bool = True,
    token_path: str | Path | None = None,
):
    env = check_env()

    if env == Environment.COLAB:
        if email is None:
            email = get_email_colab()
        if email is None:
            raise ValueError("Email is required for Colab login")
        print("email", email)
        client = SyftboxManager.for_colab(email=email, has_do_role=True)

    elif env == Environment.JUPYTER:
        token_path = token_path or settings.token_path
        if not token_path:
            raise NotImplementedError(
                "Jupyter login is only supported with a token path"
            )
        client = SyftboxManager.for_jupyter(
            email=email, has_do_role=True, token_path=token_path
        )
    else:
        raise ValueError(f"Environment {env} not supported")

    return _init_client(client, sync, load_peers)
