"""Result dataclasses returned by syft-bg API functions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from syft_bg.common.syft_bg_config import SyftBgConfig
from typing import Optional

if TYPE_CHECKING:
    from syft_bg.approve.config import AutoApprovalObj


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


class TokenStatus:
    """Displayable token status with text and HTML representations."""

    def __init__(self, label: str, path: Optional[Path]):
        self.label = label
        self.path = path
        if path is None:
            self.status = "not configured"
            self.ok = False
        elif path.exists():
            self.status = "ready"
            self.ok = True
        else:
            self.status = f"missing ({path})"
            self.ok = False

    def render(self, as_html: bool = False) -> str:
        if as_html:
            if self.ok:
                status = f'<span style="color:green">{self.status}</span>'
            elif self.path is not None:
                status = f'<span style="color:red">missing</span> ({self.path})'
            else:
                status = f'<span style="color:red">{self.status}</span>'
            return f"{self.label}: {status}"
        return f"  {self.label:<35} {self.status}"


class ServiceLine:
    """Displayable service status with text and HTML representations."""

    def __init__(self, name: str, status: str, has_setup_error: bool):
        self.name = name
        self.status = status
        self.has_setup_error = has_setup_error

    def render(self, as_html: bool = False) -> str:
        if self.has_setup_error:
            if as_html:
                return f'{self.name}: <span style="color:red">✗ setup error</span>'
            return f"  {self.name:<16} ✗ setup error"
        if as_html:
            if "running" in self.status:
                status = f'<span style="color:green">{self.status}</span>'
            else:
                status = self.status
            return f"{self.name}: {status}"
        return f"  {self.name:<16} {self.status}"


class StatusResult(BaseModel):
    """Status of syft-bg services and configuration."""

    model_config = {"arbitrary_types_allowed": True}

    config: "SyftBgConfig"
    services: dict[str, str] = Field(default_factory=dict)
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

    def _token_items(self) -> list[TokenStatus]:
        active = self.services
        items: list[TokenStatus] = []

        if "notify" in active:
            n = self.config.notify
            items.append(TokenStatus("notify.gmail_token_path", n.gmail_token_path))
            items.append(TokenStatus("notify.drive_token_path", n.drive_token_path))
        if "approve" in active:
            a = self.config.approve
            items.append(TokenStatus("approve.drive_token_path", a.drive_token_path))
        if "email_approve" in active:
            e = self.config.email_approve
            items.append(
                TokenStatus("email_approve.gmail_token_path", e.gmail_token_path)
            )

        return items

    def _service_items(self) -> list[ServiceLine]:
        from syft_bg.api.utils import load_setup_state
        from syft_bg.common.setup_state import SetupStatus

        items: list[ServiceLine] = []
        for name, s in self.services.items():
            setup = load_setup_state(name)
            has_error = bool(setup and setup.setup_status == SetupStatus.ERROR)
            items.append(ServiceLine(name, s, has_error))
        return items

    def _tokens_contents(self, as_html: bool = False) -> str:
        items = self._token_items()
        if not items:
            return "  (no active services)"
        sep = "<br>" if as_html else "\n"
        return sep.join(t.render(as_html) for t in items)

    def _services_contents(self, as_html: bool = False) -> str:
        sep = "<br>" if as_html else "\n"
        return sep.join(s.render(as_html) for s in self._service_items())

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
            line=line,
            tokens=self._tokens_contents(),
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

    def _repr_html_(self) -> str:
        env = "Colab" if self.is_colab else "local"
        tokens_html = self._tokens_contents(as_html=True)
        services_html = self._services_contents(as_html=True)

        html = "<b>syft-bg status</b><br>"
        html += f"email: {self.email or 'not configured'}<br>"
        html += f"syftbox: {self.syftbox_root or 'not configured'}<br>"
        html += f"environment: {env}<br><br>"
        html += f"<b>tokens</b><br>{tokens_html}<br><br>"
        html += f"<b>services</b><br>{services_html}"
        return html


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
