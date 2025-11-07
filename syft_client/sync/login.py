from syft_client.sync.utils.syftbox_utils import check_env
from syft_client.sync.environments.environment import Environment
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.utils.print_utils import print_client_connected
from syft_client.sync.utils.syftbox_utils import get_email_colab
from syft_client.sync.config.config import settings
from pathlib import Path


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
        client = SyftboxManager.for_colab(email=email, only_ds=True)
    elif env == Environment.JUPYTER:
        token_path = token_path or settings.token_path
        if not token_path:
            raise NotImplementedError(
                "Jupyter login is only supported with a token path"
            )
        if email is None:
            raise ValueError("Email is required for Jupyter login")

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
        client = SyftboxManager.for_colab(email=email, only_datasite_owner=True)

    elif env == Environment.JUPYTER:
        token_path = token_path or settings.token_path
        if not token_path:
            raise NotImplementedError(
                "Jupyter login is only supported with a token path"
            )
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
