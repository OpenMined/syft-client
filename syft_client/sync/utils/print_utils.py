from syft_client.sync.syftbox_manager import SyftboxManager


def print_client_connected(client: SyftboxManager):
    platforms_str = ", ".join(
        [platform.name for platform in client._get_all_peer_platforms()]
    )
    n_peers = len(client.peers)
    print(f"✅ Connected peer-to-peer to {n_peers} peers via: {platforms_str}")
