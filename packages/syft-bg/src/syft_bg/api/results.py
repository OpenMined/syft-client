"""Result dataclasses returned by syft-bg API functions."""

from pathlib import Path

from pydantic import BaseModel, Field


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

    email: str | None = None
    syftbox_root: str | None = None
    services: dict[str, str] = Field(default_factory=dict)
    email_configured: bool = False
    auto_approvals: dict[str, dict] = Field(default_factory=dict)
    approved_domains: list[str] = Field(default_factory=list)
    is_colab: bool = False

    def __repr__(self) -> str:
        lines = ["syft-bg status"]
        lines.append("=" * 40)

        lines.append(f"  email:       {self.email or 'not configured'}")
        lines.append(f"  syftbox:     {self.syftbox_root or 'not configured'}")
        lines.append(f"  environment: {'Colab' if self.is_colab else 'local'}")
        lines.append(
            f"  gmail:       {'ready' if self.email_configured else 'not set up'}"
        )

        lines.append("")
        lines.append("services")
        lines.append("-" * 40)
        for name, svc_status in self.services.items():
            lines.append(f"  {name:<12} {svc_status}")

        if self.auto_approvals:
            lines.append("")
            lines.append("auto-approval objects")
            lines.append("-" * 40)
            for obj_name, obj_data in self.auto_approvals.items():
                lines.append(f"  [{obj_name}]")
                for entry in obj_data.get("file_contents", []):
                    lines.append(f"    content: {entry}")
                for fname in obj_data.get("file_paths", []):
                    lines.append(f"    file:   {fname}")
                peers = obj_data.get("peers", [])
                if peers:
                    lines.append(f"    peers:  {', '.join(peers)}")
                else:
                    lines.append("    peers:  (any)")

        if self.approved_domains:
            lines.append("")
            lines.append("auto-approved domains")
            lines.append("-" * 40)
            for domain in self.approved_domains:
                lines.append(f"  {domain}")

        return "\n".join(lines)


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
