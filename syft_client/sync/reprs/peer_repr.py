from io import StringIO
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from syft_client.sync.peers.peer import Peer, PeerState


def get_peer_list_table(peers: list[Peer]) -> str:
    console = Console(
        file=StringIO(),
        record=True,
        force_jupyter=False,
    )

    # Split by state
    approved_peers = [p for p in peers if p.state == PeerState.ACCEPTED]
    pending_peers = [p for p in peers if p.state == PeerState.PENDING]

    # Create main table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(width=None)

    # Section: Approved peers
    table.add_row("[bold green]client.peers[/]  [dim green]\\[0] or ['email'][/]")

    # Add each approved peer
    for i, p in enumerate(approved_peers):
        platform_modules = [plat.module_name for plat in p.platforms]
        table.add_row(
            f"  [dim black]\\[{i}][/] [black]{p.email}[/]         [green]✓[/] [black]{', '.join(platform_modules)}[/]"
        )

    # Add empty row for spacing
    table.add_row("")

    # Section: Pending requests
    if pending_peers:
        table.add_row(
            f"[bold yellow]client.peers.requests[/]  [dim yellow]{len(pending_peers)} pending[/]"
        )
        for i, p in enumerate(pending_peers):
            platform_modules = [plat.module_name for plat in p.platforms]
            idx = len(approved_peers) + i
            table.add_row(
                f"  [dim black]\\[{idx}][/] [yellow]{p.email}[/]         [yellow]?[/] [black]{', '.join(platform_modules)}[/]"
            )
    else:
        table.add_row("[bold yellow]client.peers.requests[/]  [dim yellow]None[/]")

    table.add_row("")

    # Wrap in panel with updated count
    panel = Panel(
        table,
        title=f"Peers & Requests  ({len(approved_peers)} active, {len(pending_peers)} pending)",
        expand=False,
        border_style="dim",
    )

    console.print(panel)
    return console.export_html(inline_styles=True)
