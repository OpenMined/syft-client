from syft_client.sync.peers.peer import Peer
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


def print_client_connected(client: "SyftboxManager"):
    # PERFORMANCE: Skip expensive peer query during login
    # Just print a simple message instead
    print(f"✅ Client connected successfully")


def print_peer_adding_to_platform(peer_email: str, platform_str: str):
    print(f"🔄 Adding {peer_email} on {platform_str}...")


def print_peer_added_to_platform(peer_email: str, platform_str: str):
    print(f"✅ Added {peer_email} to {platform_str}")


def print_peer_added(peer: Peer):
    print(
        f"✅ Peer {peer.email} added successfully on {len(peer.platforms)} transport(s)"
    )
    for platform in peer.platforms:
        print(f"• {platform.module_path}")
