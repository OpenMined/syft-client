from syft_client.sync.peers.peer import Peer
from syft_client.sync.utils.syftbox_utils import check_env
from syft_client.sync.environments.environment import Environment
from syft_client.version import SYFT_CLIENT_VERSION
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


def print_client_connecting(email: str):
    is_colab = check_env() == Environment.COLAB
    print(f"🔑 Logging in as {email}...")
    print(f"   Environment: {'Colab' if is_colab else 'Python'}")


def print_client_connected(client: "SyftboxManager"):
    print("\n✅ Logged in successfully!")
    print(f"   SyftBox folder : {client.syftbox_folder}")
    print(f"   Version        : {SYFT_CLIENT_VERSION}")

    peers = client.peer_manager.approved_peers
    if peers:
        print(f"\n👥 {len(peers)} peer(s) restored from previous session.")
        print("   Run client.sync() to pull the latest updates.")
    else:
        print("\n💡 No peers yet. Add a Data Owner with:")
        print("   client.add_peer('do@org.com')")


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
