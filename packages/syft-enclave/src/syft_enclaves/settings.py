from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Fallback SyftBox root, used for local development. In a container the
#: deployment provisions the storage location and sets it explicitly.
DEFAULT_SYFTBOX_FOLDER = Path.home() / "SyftBox"


class EnclaveSettings(BaseSettings):
    """Runtime configuration for ``python -m syft_enclaves``.

    Every field maps to an environment variable with a ``SYFT_ENCLAVE_``
    prefix (e.g. ``email`` is read from ``SYFT_ENCLAVE_EMAIL``). Values may
    also be placed in a ``.env`` file in the working directory.

    Example ``.env`` for local development::

        SYFT_ENCLAVE_EMAIL=enclave@openmined.org
        SYFT_ENCLAVE_SYFTBOX_FOLDER=/tmp/enclave-syftbox
        SYFT_ENCLAVE_TOKEN_PATH=/secrets/gdrive_token.json
        SYFT_ENCLAVE_REQUIRE_TEE=false
    """

    model_config = SettingsConfigDict(
        env_prefix="SYFT_ENCLAVE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    email: str = Field(
        description="Email address of the enclave datasite. Required.",
    )
    syftbox_folder: Path = Field(
        default=DEFAULT_SYFTBOX_FOLDER,
        description=(
            "Root SyftBox folder. Provisioned by the deployment inside a "
            "container; any writable path when running locally."
        ),
    )
    # TODO: this is temporary and only for testing, this will be replaced
    # with a secrets management solution or passing the token value via environment variable for testing.
    token_path: Path = Field(
        description=("Filesystem path to a pre-authorized Google Drive OAuth token. "),
    )
    poll_interval: int = Field(
        default=10,
        ge=1,
        description="Seconds to wait between poll-loop cycles.",
    )
    require_tee: bool = Field(
        default=False,
        description=(
            "Refuse to start unless a Confidential Spaces TEE socket is "
            "present. Set true in production, false for local testing."
        ),
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Root logging level.",
    )
