from syft_client.sync.peers.peer import Peer, PeerState
from syft_client.sync.reprs.peer_repr import get_peer_list_table


class PeerList(list):
    def __init__(self, *args: Peer, **kwargs):
        """
        PeerList is a list specifically for Peer objects.
        Validates that all items are Peer objects and that they are sorted correctly.
        """
        super().__init__(*args, **kwargs)
        # Validate all items are Peer objects
        for item in self:
            if not isinstance(item, Peer):
                raise TypeError(
                    f"All items in PeerList must be Peer objects, but got {type(item)}"
                )
        # Validate sorting (approved before pending)
        self._validate_sorting()

    def _validate_sorting(self):
        """Ensure approved peers come before pending requests"""
        seen_request = False
        for peer in self:
            if peer.state == PeerState.PENDING:
                seen_request = True
            elif peer.state == PeerState.ACCEPTED and seen_request:
                raise ValueError(
                    "PeerList must be sorted: approved peers first, then requests"
                )

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
