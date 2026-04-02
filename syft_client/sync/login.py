import sys
import warnings

from syft_client.sync.utils.syftbox_utils import check_env
from syft_client.sync.environments.environment import Environment
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.utils.print_utils import print_client_connected
from syft_client.sync.utils.syftbox_utils import get_email_colab
from syft_client.sync.config.config import settings
from syft_client.version import SYFT_CLIENT_VERSION
from pathlib import Path


def _check_existing_state_version(client: SyftboxManager) -> None:
    """Check if existing SyftBox state on GDrive has a different version.

    If a SYFT_version.json exists and its syft_client_version differs from the
    currently installed version, prompt the user to choose:
      1. Delete old state and start fresh
      2. Quit
      3. Continue anyway (with a compatibility warning)
    """
    existing_version = client.read_own_version()
    if existing_version is None:
        return

    if existing_version.syft_client_version == SYFT_CLIENT_VERSION:
        return

    print(
        f"\n⚠️  Existing SyftBox state found (version {existing_version.syft_client_version}), "
        f"but you are running version {SYFT_CLIENT_VERSION}.\n"
    )
    print("  [1] Delete old state and start fresh")
    print("  [2] Quit")
    print("  [3] Continue anyway (may cause compatibility issues)\n")

    choice = input("Choice [1/2/3]: ").strip()

    if choice == "1":
        print("Deleting old SyftBox state...")
        client.delete_syftbox(verbose=True, broadcast_delete_events=False)
        # Reset peer manager's connection caches so write_own_version
        # doesn't try to use the now-deleted SyftBox folder ID
        client.peer_manager.connection_router.reset_caches()
        print("Old state deleted. Continuing with fresh setup.\n")
    elif choice == "2":
        print("Exiting.")
        sys.exit(0)
    elif choice == "3":
        warnings.warn(
            f"Continuing with mismatched versions "
            f"(state={existing_version.syft_client_version}, "
            f"installed={SYFT_CLIENT_VERSION}). "
            "You may encounter compatibility issues.",
            stacklevel=2,
        )
    else:
        print(f"Invalid choice '{choice}'. Exiting.")
        sys.exit(1)


def _init_client(client: SyftboxManager, sync: bool, load_peers: bool) -> SyftboxManager:
    """Common post-creation initialization: version check, write version, sync, load peers."""
    _check_existing_state_version(client)
    client.write_own_version()

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
