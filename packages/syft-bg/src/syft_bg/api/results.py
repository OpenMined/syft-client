"""Result dataclasses returned by syft-bg API functions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from syft_bg.approve.config import AutoApprovalObj
    from syft_bg.common.syft_bg_config import SyftBgConfig


class InitResult(BaseModel):
    """Result of init() call."""

    success: bool
    config_path: Path | None = None
    error: str | None = None
    services: dict[str, tuple[bool, str]] | None = None
    issues: list[str] = Field(default_factory=list)

    def __repr__(self) -> str:
        lines = []
        if self.success:
            lines.append("InitResult: OK")
            if self.config_path:
                lines.append(f"  config: {self.config_path}")
            if self.services:
                for name, (ok, msg) in self.services.items():
                    status = "started" if ok else "failed"
                    lines.append(f"  {name}: {status} — {msg}")
        else:
            lines.append("InitResult: FAILED")
            if self.error:
                lines.append(f"  error: {self.error}")
        if self.issues:
            lines.append("  issues:")
            for issue in self.issues:
                indented = issue.replace("\n", "\n      ")
                lines.append(f"    - {indented}")
        return "\n".join(lines)


class AuthResult(BaseModel):
    """Result of authenticate() call."""

    success: bool
    gmail_ok: bool = False
    drive_ok: bool = False
    error: str | None = None

    def __repr__(self) -> str:
        lines = []
        if self.success:
            lines.append("AuthResult: OK")
        else:
            lines.append("AuthResult: FAILED")
            if self.error:
                lines.append(f"  error: {self.error}")
        lines.append(f"  gmail: {'ready' if self.gmail_ok else 'missing'}")
        lines.append(f"  drive: {'ready' if self.drive_ok else 'missing'}")
        return "\n".join(lines)


class StatusResult(BaseModel):
    """Status of syft-bg services and configuration."""

    model_config = {"arbitrary_types_allowed": True}

    config: "SyftBgConfig"
    services: dict[str, str] = Field(default_factory=dict)
    email_configured: bool = False
    is_colab: bool = False

    @property
    def email(self) -> str | None:
        return self.config.do_email

    @property
    def syftbox_root(self) -> str | None:
        return self.config.syftbox_root

    @property
    def auto_approvals(self) -> dict[str, "AutoApprovalObj"]:
        return self.config.approve.auto_approvals.objects

    @property
    def approved_domains(self) -> list[str]:
        return self.config.approve.peers.approved_domains

    def _services_contents(self) -> str:
        return "\n".join(f"  {name:<12} {s}" for name, s in self.services.items())

    def _auto_approval_obj_contents(self, name: str, obj: AutoApprovalObj) -> str:
        contents = "\n".join(
            f"    content: {e.relative_path}" for e in obj.file_contents
        )
        files = "\n".join(f"    file:   {f}" for f in obj.file_paths)
        peers = (
            f"    peers:  {', '.join(obj.peers)}" if obj.peers else "    peers:  (any)"
        )
        body = "\n".join(part for part in [contents, files, peers] if part)
        return f"  [{name}]\n{body}"

    def _auto_approvals_contents(self) -> str:
        return "\n".join(
            self._auto_approval_obj_contents(name, obj)
            for name, obj in self.auto_approvals.items()
        )

    def _approved_domains_contents(self) -> str:
        return "\n".join(f"  {d}" for d in self.approved_domains)

    def __repr__(self) -> str:
        from syft_bg.api.templates import (
            APPROVED_DOMAINS_SECTION,
            AUTO_APPROVALS_SECTION,
            STATUS_TEMPLATE,
        )

        line = "-" * 40
        result = STATUS_TEMPLATE.format(
            sep="=" * 40,
            email=self.email or "not configured",
            syftbox_root=self.syftbox_root or "not configured",
            env="Colab" if self.is_colab else "local",
            gmail="ready" if self.email_configured else "not set up",
            line=line,
            services=self._services_contents(),
        )

        if self.auto_approvals:
            result += AUTO_APPROVALS_SECTION.format(
                line=line, contents=self._auto_approvals_contents()
            )

        if self.approved_domains:
            result += APPROVED_DOMAINS_SECTION.format(
                line=line, contents=self._approved_domains_contents()
            )

        return result


class AutoApproveResult(BaseModel):
    """Result of auto_approve() call."""

    success: bool
    name: str = ""
    file_contents: list[str] = Field(default_factory=list)
    file_paths: list[str] = Field(default_factory=list)
    peers: list[str] = Field(default_factory=list)
    error: str | None = None

    def __repr__(self) -> str:
        lines = []
        if self.success:
            lines.append(f"AutoApproveResult: OK [{self.name}]")
            if self.file_contents:
                lines.append("  file_contents:")
                for s in self.file_contents:
                    lines.append(f"    - {s}")
            if self.file_paths:
                lines.append(f"  file_paths: {', '.join(self.file_paths)}")
            if self.peers:
                lines.append(f"  peers: {', '.join(self.peers)}")
            else:
                lines.append("  peers: (any)")
        else:
            lines.append("AutoApproveResult: FAILED")
            if self.error:
                lines.append(f"  error: {self.error}")
        return "\n".join(lines)
