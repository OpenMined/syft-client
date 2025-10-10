"""
Peer resource model for transport-specific resources
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class PeerResource:
    """Represents a peer's resources on a specific transport"""

    peer_email: str
    transport_name: str
    platform_name: str

    # Resource details
    pending: Optional[Dict[str, Any]] = None
    outbox_inbox: Optional[Dict[str, Any]] = None
    archive: Optional[Dict[str, Any]] = None

    # For transports without folders (like Gmail)
    resource_type: str = "folders"
    available: bool = True

    @property
    def has_folders(self) -> bool:
        """Check if this resource has folder structure"""
        return any([self.pending, self.outbox_inbox, self.archive])

    @property
    def all_folders(self) -> List[Dict[str, Any]]:
        """Get all non-None folders"""
        folders = []
        if self.pending:
            folders.append({"type": "pending", **self.pending})
        if self.outbox_inbox:
            folders.append({"type": "outbox_inbox", **self.outbox_inbox})
        if self.archive:
            folders.append({"type": "archive", **self.archive})
        return folders

    def __repr__(self) -> str:
        """Rich representation of peer resources"""
        from io import StringIO

        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=80)

        # Create main table
        table = Table(show_header=False, show_edge=False, box=None, padding=0)
        table.add_column("", no_wrap=False)

        # Header
        table.add_row(f"[bold cyan]Peer:[/bold cyan] {self.peer_email}")
        table.add_row(
            f"[bold cyan]Transport:[/bold cyan] {self.platform_name}.{self.transport_name}"
        )

        if self.has_folders:
            table.add_row("")
            table.add_row("[bold]Communication Folders:[/bold]")

            # Show each folder
            if self.pending:
                table.add_row("")
                table.add_row(f"[yellow]📁 Pending (Private):[/yellow]")
                table.add_row(f"   [dim]{self.pending.get('name', 'Unknown')}[/dim]")
                if self.pending.get("url"):
                    table.add_row(
                        f"   [link={self.pending['url']}]→ Open in Drive[/link]"
                    )

            if self.outbox_inbox:
                table.add_row("")
                table.add_row(f"[green]📤 Outbox/Inbox (Shared):[/green]")
                table.add_row(
                    f"   [dim]{self.outbox_inbox.get('name', 'Unknown')}[/dim]"
                )
                if self.outbox_inbox.get("url"):
                    table.add_row(
                        f"   [link={self.outbox_inbox['url']}]→ Open in Drive[/link]"
                    )

                # Show permissions
                permissions = self.outbox_inbox.get("permissions", [])
                if permissions:
                    table.add_row("   [dim]Shared with:[/dim]")
                    for perm in permissions:
                        email = perm.get("emailAddress", "Unknown")
                        role = perm.get("role", "Unknown")
                        if email != self.peer_email:  # Don't show owner
                            table.add_row(f"     • {email} ({role})")

            if self.archive:
                table.add_row("")
                table.add_row(f"[blue]📥 Archive (Shared):[/blue]")
                table.add_row(f"   [dim]{self.archive.get('name', 'Unknown')}[/dim]")
                if self.archive.get("url"):
                    table.add_row(
                        f"   [link={self.archive['url']}]→ Open in Drive[/link]"
                    )
        else:
            # Non-folder resources (like Gmail)
            table.add_row("")
            table.add_row(f"[dim]Type: {self.resource_type}[/dim]")
            table.add_row(f"[dim]Available: {'Yes' if self.available else 'No'}[/dim]")

        # Create panel
        panel = Panel(
            table,
            title=f"{self.transport_name.title()} Resources",
            expand=False,
            width=80,
            padding=(1, 2),
        )

        console.print(panel)
        return string_buffer.getvalue().strip()


__all__ = ["PeerResource"]
