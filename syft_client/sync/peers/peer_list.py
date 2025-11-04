from syft_client.sync.peers.peer import Peer
from syft_client.sync.reprs.peer_repr import get_peer_list_table


class PeerList(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __getitem__(self, index: str | int) -> Peer:
        if isinstance(index, int):
            return super().__getitem__(index)
        elif isinstance(index, str):
            key = index
            for peer in self:
                if peer.email == key:
                    return peer
            raise ValueError(f"Peer with email {index} not found")
        else:
            raise ValueError(f"Invalid index type: {type(index)}")

    def _repr_html_(self) -> str:
        """Used by Jupyter to display Rich HTML."""
        peers = [p for p in self]
        return get_peer_list_table(peers)

    def __repr__(self):
        """Fallback for normal REPL"""
        peers = [p for p in self]
        return f"PeerList({peers!r})"
