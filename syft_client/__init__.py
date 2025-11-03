"""
syft_client - A unified client for secure file syncing
"""

__version__ = "0.1.88"

from syft_client.sync.utils.syftbox_utils import check_env
from syft_client.sync.environments.environment import Environment
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.utils.print_utils import print_client_connected
from syft_client.sync.utils.syftbox_utils import get_email_colab
from syft_client.sync.config.config import settings


def login(email: str | None = None, sync: bool = True, load_peers: bool = True):
    return login_ds(email, sync, load_peers)


def login_ds(email: str | None = None, sync: bool = True, load_peers: bool = True):
    env = check_env()

    if env == Environment.COLAB:
        if email is None:
            email = get_email_colab()
        client = SyftboxManager.for_colab(email=email, only_ds=True)
    elif env == Environment.JUPYTER:
        if not settings.dev_mode:
            raise NotImplementedError("Jupyter login is not implemented yet")
        if email is None:
            raise ValueError("Email is required for Jupyter login")

        token_path = settings.token_path
        client = SyftboxManager.for_jupyter(
            email=email, only_ds=True, token_path=token_path
        )
    else:
        raise ValueError(f"Environment {env} not supported")

    if sync:
        client.sync()
    if load_peers:
        client.load_peers()
    print_client_connected(client)
    return client


def login_do(email: str | None = None, sync: bool = True, load_peers: bool = True):
    env = check_env()

    if env == Environment.COLAB:
        if email is None:
            email = get_email_colab()

    elif env == Environment.JUPYTER:
        if not settings.dev_mode:
            raise NotImplementedError("Jupyter login is not implemented yet")
        token_path = settings.token_path
        client = SyftboxManager.for_jupyter(
            email=email, only_datasite_owner=True, token_path=token_path
        )
    else:
        raise ValueError(f"Environment {env} not supported")

    if sync:
        client.sync()
    if load_peers:
        client.load_peers()
    print_client_connected(client)
    return client
