from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnclaveSettings(BaseSettings):
    """Runtime configuration for ``python -m syft_enclaves``.

    Every field maps to an environment variable with a ``SYFT_ENCLAVE_``
    prefix (e.g. ``email`` is read from ``SYFT_ENCLAVE_EMAIL``). Values may
    also be placed in a ``.env`` file in the working directory.

    Example ``.env`` for local development::

        SYFT_ENCLAVE_EMAIL=enclave@openmined.org
        SYFT_ENCLAVE_SYFTBOX_FOLDER=/tmp/enclave-syftbox
        SYFT_ENCLAVE_TOKEN_PATH=/secrets/gdrive_token.json   # optional
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
    syftbox_folder: Path | None = Field(
        default=None,
        description=(
            "Root SyftBox folder. Provisioned by the deployment inside a "
            "container; any writable path when running locally."
        ),
    )
    # Default coupled with docker/entrypoint.sh, which writes the
    # operator-supplied token to this exact path before the runner starts.
    token_path: Path = Field(
        default=Path("/run/syft-enclave/token.json"),
        description=(
            "Filesystem path to a pre-authorized Google Drive OAuth token. "
            "In production, docker/entrypoint.sh writes the token content "
            "shipped via SYFT_ENCLAVE_TOKEN_CONTENT to this path before the "
            "runner starts."
        ),
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
