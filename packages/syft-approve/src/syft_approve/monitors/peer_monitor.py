from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

from syft_approve.handlers.peer_handler import PeerApprovalHandler, StateManager
from syft_approve.monitors.base import Monitor

if TYPE_CHECKING:
    from syft_approve.core.config import PeerApprovalConfig
    from syft_client.sync.syftbox_manager import SyftboxManager


class PeerMonitor(Monitor):
    def __init__(
        self,
        client: SyftboxManager,
        config: PeerApprovalConfig,
        state: Optional[StateManager] = None,
        on_approve: Optional[Callable[[str], None]] = None,
        verbose: bool = True,
    ):
        self.handler = PeerApprovalHandler(
            client=client,
            config=config,
            state=state,
            on_approve=on_approve,
            verbose=verbose,
        )

    def _check_all_entities(self):
        self.handler.check_and_approve()
