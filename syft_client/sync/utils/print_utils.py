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


def print_peer_request_sending(peer_email: str) -> None:
    print(f"🤝 Sending peer request to {peer_email}...")


def print_peer_request_resending(peer_email: str) -> None:
    print(f"♻️  Resending peer request to {peer_email}...")


def print_peer_request_accepting(peer_email: str) -> None:
    print(f"🤝 Accepting peer request from {peer_email}...")


def print_peer_request_sent(peer_email: str) -> None:
    print(f"\n✅ Peer request sent to {peer_email}!")
    print("   ⏳ Next step: ask them to approve your request.")
    print("   Once approved, run client.sync() to confirm the connection.")


def print_peer_connection_established(peer_email: str) -> None:
    print(f"\n✅ Connection with {peer_email} established!")
    print("   Run client.sync() to start syncing.")


def print_peer_already_connected(peer_email: str, state: str) -> None:
    print(f"ℹ️  Already have a connection with {peer_email} (state: {state}).")
    print("   Use force=True to resend the request.")
