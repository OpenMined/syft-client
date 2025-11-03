from syft_client.sync.peers.peer import Peer
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


def print_client_connected(client: "SyftboxManager"):
    platforms_str = ", ".join(
        [platform.name for platform in client._get_all_peer_platforms()]
    )
    n_peers = len(client.peers)
    if n_peers > 0:
        print(f"✅ Connected peer-to-peer to {n_peers} peers via: {platforms_str}")
    else:
        print(f"✅ Connected to {n_peers} peers")


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
