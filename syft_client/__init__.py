"""
syft_client - A unified client for secure file syncing
"""

from syft_client.sync.syftbox_utils import check_env
from syft_client.sync.environments.environment import Environment
from syft_client.sync.syftbox_manager import SyftboxManager


def login_do(email: str):
    env = check_env()

    if env == Environment.COLAB:
        SyftboxManager.for_colab(email=email)
    elif env == Environment.JUPYTER:
        raise NotImplementedError("Jupyter login is not implemented yet")
        SyftboxManager.for_jupyter(email=email)
    else:
        raise ValueError(f"Environment {env} not supported")


# Class SyftManager():


#     @classmethod
#     def for_jupyter(cls, email: str):
#         creds = authenticate(email=email, platforms=["gdrive"])
#         cls(creds=creds)
