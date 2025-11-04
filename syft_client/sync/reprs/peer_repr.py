from io import StringIO
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from syft_client.sync.peers.peer import Peer


def get_peer_list_table(peers: list[Peer]) -> str:
    console = Console(
        file=StringIO(),
        record=True,
        force_jupyter=False,
    )

    # Create main table
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(width=None)

    # Section header
    table.add_row("[bold green]client.peers[/]  [dim green]\\[0] or ['email'][/]")

    # Add each peer
    for i, p in enumerate(peers):
        platform_modules = [plat.module_name for plat in p.platforms]
        table.add_row(
            f"  [dim black]\\[{i}][/] [black]{p.email}[/]         [green]✓[/] [black]{', '.join(platform_modules)}[/]"
        )

    # Add empty row for spacing
    table.add_row("")

    # Requests section
    table.add_row("[bold yellow]client.peers.requests[/]  [dim yellow]None[/]")
    table.add_row("")

    # Wrap in panel
    panel = Panel(
        table,
        title=f"Peers & Requests  ({len(peers)} active, 0 pending)",
        expand=False,
        border_style="dim",
    )

    console.print(panel)
    return console.export_html(inline_styles=True)
