"""Peer monitor for detecting new peer requests."""

from typing import TYPE_CHECKING

from syft_bg.common.monitor import Monitor
from syft_bg.common.state import JsonStateManager
from syft_bg.notify.handlers.peer import PeerHandler

if TYPE_CHECKING:
    from syft_bg.sync.snapshot_reader import SnapshotReader


class PeerMonitor(Monitor):
    """Monitors for new peer requests via sync snapshot."""

    def __init__(
        self,
        do_email: str,
        handler: PeerHandler,
        state: JsonStateManager,
        snapshot_reader: "SnapshotReader",
    ):
        super().__init__()
        self.do_email = do_email
        self.handler = handler
        self.state = state
        self.snapshot_reader = snapshot_reader

    def _check_all_entities(self):
        snapshot = self.snapshot_reader.read()
        if not snapshot:
            return

        current_peer_emails = set(snapshot.peer_emails)
        previous_peer_emails = set(self.state.get_data("peer_snapshot", []))
        new_peer_emails = current_peer_emails - previous_peer_emails

        if new_peer_emails:
            print(f"[PeerMonitor] Detected {len(new_peer_emails)} new peer(s)")

        for peer_email in new_peer_emails:
            self._handle_new_peer(peer_email)

        self.state.set_data("peer_snapshot", list(current_peer_emails))

        self._check_approved_peers(snapshot)

    def _check_approved_peers(self, snapshot):
        approved_peers = set(snapshot.approved_peer_emails)

        for peer_email in approved_peers:
            state_key = f"peer_granted_{peer_email}"
            if not self.state.was_notified(state_key, "peer_granted"):
                success = self.handler.on_peer_granted(peer_email, self.do_email)
                if success:
                    print(
                        f"[PeerMonitor] Sent peer granted notification to {peer_email}"
                    )

    def _handle_new_peer(self, ds_email: str):
        success = self.handler.on_new_peer_request_to_do(self.do_email, ds_email)
        if success:
            print(f"[PeerMonitor] Sent new peer request notification to DO: {ds_email}")

        success = self.handler.on_peer_request_sent(ds_email, self.do_email)
        if success:
            print(
                f"[PeerMonitor] Sent peer request sent notification to DS: {ds_email}"
            )

    def notify_peer_granted(self, ds_email: str) -> bool:
        success = self.handler.on_peer_granted(ds_email, self.do_email)
        if success:
            print(f"[PeerMonitor] Sent peer granted notification to DS: {ds_email}")
        return success
