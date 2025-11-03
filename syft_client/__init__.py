"""
syft_client - A unified client for secure file syncing
"""

from syft_client.sync.syftbox_utils import check_env
from syft_client.sync.environments.environment import Environment
from syft_client.sync.syftbox_manager import SyftboxManager


# def login(email: str):
#     login_ds(email)


# def login_ds(email: str):
#     print("login_ds not implemented yet")


def login_do(email: str):
    env = check_env()

    if env == Environment.COLAB:
        return SyftboxManager.for_colab(email=email, only_datasider_owner=True)
    elif env == Environment.JUPYTER:
        raise NotImplementedError("Jupyter login is not implemented yet")
        # SyftboxManager.for_jupyter(email=email)
    else:
        raise ValueError(f"Environment {env} not supported")
