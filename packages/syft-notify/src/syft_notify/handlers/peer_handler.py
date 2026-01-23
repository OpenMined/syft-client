from typing import Optional

from syft_notify.core.base import NotificationSender, StateManager


class PeerHandler:
    def __init__(
        self,
        sender: NotificationSender,
        state: StateManager,
        notify_on_new_peer: bool = True,
        notify_on_peer_granted: bool = True,
    ):
        self.sender = sender
        self.state = state
        self.notify_on_new_peer = notify_on_new_peer
        self.notify_on_peer_granted = notify_on_peer_granted

    def on_new_peer_request_to_do(
        self,
        do_email: str,
        ds_email: str,
        peer_url: Optional[str] = None,
    ) -> bool:
        if not self.notify_on_new_peer:
            return False

        state_key = f"peer_new_{ds_email}_to_do"
        if self.state.was_notified(state_key, "new_peer_request"):
            return False

        if hasattr(self.sender, "notify_new_peer_request_to_do"):
            success = self.sender.notify_new_peer_request_to_do(
                do_email, ds_email, peer_url
            )
        else:
            success = self.sender.send_notification(
                do_email,
                f"New Peer Request from {ds_email}",
                f"You have a new peer request from {ds_email}",
            )

        if success:
            self.state.mark_notified(state_key, "new_peer_request")

        return success

    def on_peer_request_sent(
        self,
        ds_email: str,
        do_email: str,
    ) -> bool:
        if not self.notify_on_new_peer:
            return False

        state_key = f"peer_new_{ds_email}_to_ds"
        if self.state.was_notified(state_key, "peer_request_sent"):
            return False

        if hasattr(self.sender, "notify_peer_request_sent"):
            success = self.sender.notify_peer_request_sent(ds_email, do_email)
        else:
            success = self.sender.send_notification(
                ds_email,
                f"Peer Request Sent to {do_email}",
                f"Your peer request to {do_email} has been received.",
            )

        if success:
            self.state.mark_notified(state_key, "peer_request_sent")

        return success

    def on_peer_added(
        self,
        ds_email: str,
        do_email: str,
    ) -> bool:
        if not self.notify_on_new_peer:
            return False

        state_key = f"peer_added_{ds_email}_{do_email}"
        if self.state.was_notified(state_key, "peer_added"):
            return False

        if hasattr(self.sender, "notify_peer_added_to_ds"):
            success = self.sender.notify_peer_added_to_ds(ds_email, do_email)
        else:
            success = self.sender.send_notification(
                ds_email,
                f"Peer Added: {do_email}",
                f"You successfully added {do_email} as a peer.",
            )

        if success:
            self.state.mark_notified(state_key, "peer_added")

        return success

    def on_peer_granted(
        self,
        ds_email: str,
        do_email: str,
    ) -> bool:
        if not self.notify_on_peer_granted:
            return False

        state_key = f"peer_granted_{ds_email}"
        if self.state.was_notified(state_key, "peer_granted"):
            return False

        if hasattr(self.sender, "notify_peer_request_granted"):
            success = self.sender.notify_peer_request_granted(ds_email, do_email)
        else:
            success = self.sender.send_notification(
                ds_email,
                f"Peer Request Accepted by {do_email}",
                f"{do_email} has accepted your peer request.",
            )

        if success:
            self.state.mark_notified(state_key, "peer_granted")

        return success
