"""Login helpers for enclave-flow participants."""

from pathlib import Path

from syft_client.sync.environments.environment import Environment
from syft_client.sync.login import _init_client_login, _resolve_login_params
from syft_client.sync.login_utils import handle_potential_version_mismatches_on_login
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.utils.syftbox_utils import check_env

from syft_enclaves.client import SyftEnclaveClient
from syft_enclaves.enclave_job_client import EnclaveJobClient


def _login(
    *,
    email: str | None,
    token_path: str | Path | None,
    sync: bool,
    load_peers: bool,
    skip_peer_on_patch_version_diff: bool | None,
    has_do_role: bool,
    has_ds_role: bool,
    wrap_job_client: bool,
) -> SyftEnclaveClient:
    """Shared login for enclave-flow participants.

    Mirrors ``syft_client.login_do``: detect the environment, resolve params,
    run the login-time version-mismatch check, then build the manager for
    Colab or Jupyter — but with the enclave actor's role combination.
    """
    env = check_env()
    email, token_path = _resolve_login_params(email, token_path)
    handle_potential_version_mismatches_on_login(email, token_path)

    if env == Environment.COLAB:
        manager = SyftboxManager.for_colab(
            email=email,
            has_do_role=has_do_role,
            has_ds_role=has_ds_role,
            skip_peer_on_patch_version_diff=skip_peer_on_patch_version_diff,
        )
    else:
        manager = SyftboxManager.for_jupyter(
            email=email,
            has_do_role=has_do_role,
            has_ds_role=has_ds_role,
            token_path=token_path,
            skip_peer_on_patch_version_diff=skip_peer_on_patch_version_diff,
        )

    if wrap_job_client:
        # The data scientist submits jobs — wrap the job client so
        # submit_python_job tags them as enclave jobs.
        manager.job_client = EnclaveJobClient(manager.job_client)

    # Reuses syft-client's login init: verifies the token authenticates as
    # `email`, writes the local version, then syncs / loads peers.
    _init_client_login(manager, sync=sync, load_peers=load_peers)
    return SyftEnclaveClient(manager)


def login_do(
    email: str | None = None,
    token_path: str | Path | None = None,
    sync: bool = True,
    load_peers: bool = True,
    skip_peer_on_patch_version_diff: bool | None = None,
) -> SyftEnclaveClient:
    """Log in a data owner for an enclave computation."""
    return _login(
        email=email,
        token_path=token_path,
        sync=sync,
        load_peers=load_peers,
        skip_peer_on_patch_version_diff=skip_peer_on_patch_version_diff,
        has_do_role=True,
        has_ds_role=True,
        wrap_job_client=False,
    )


def login_ds(
    email: str | None = None,
    token_path: str | Path | None = None,
    sync: bool = True,
    load_peers: bool = True,
    skip_peer_on_patch_version_diff: bool | None = None,
) -> SyftEnclaveClient:
    """Log in a data scientist for an enclave computation."""
    return _login(
        email=email,
        token_path=token_path,
        sync=sync,
        load_peers=load_peers,
        skip_peer_on_patch_version_diff=skip_peer_on_patch_version_diff,
        has_do_role=False,
        has_ds_role=True,
        wrap_job_client=True,
    )
