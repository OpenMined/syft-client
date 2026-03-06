from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.peers.peer import Peer
from syft_client.sync.peers.peer_list import PeerList
from syft_datasets.dataset_manager import SyftDatasetManager

from syft_enclaves.utils import (
    create_configs,
    create_managers,
    setup_callbacks,
    setup_connections,
    wire_peers,
    write_versions,
)


class SyftEnclaveClient:
    def __init__(self, manager: SyftboxManager):
        self._manager = manager

    @property
    def email(self) -> str:
        return self._manager.email

    @property
    def peers(self) -> PeerList:
        return self._manager.peers

    def add_peer(self, peer_email: str, force: bool = False, verbose: bool = True):
        self._manager.add_peer(peer_email, force=force, verbose=verbose)

    def load_peers(self):
        self._manager.load_peers()

    def approve_peer_request(
        self,
        email_or_peer: str | Peer,
        verbose: bool = True,
        peer_must_exist: bool = True,
    ):
        self._manager.approve_peer_request(
            email_or_peer, verbose=verbose, peer_must_exist=peer_must_exist
        )

    def reject_peer_request(self, email_or_peer: str | Peer):
        self._manager.reject_peer_request(email_or_peer)

    def sync(self):
        self._manager.sync()

    def create_dataset(self, *args, **kwargs):
        return self._manager.create_dataset(*args, **kwargs)

    def share_private_dataset(self, tag: str, enclave_email: str):
        self._manager.share_private_dataset(tag, enclave_email)

    @property
    def datasets(self) -> SyftDatasetManager:
        return self._manager.dataset_manager

    @classmethod
    def quad_with_mock_drive_service_connection(
        cls,
        enclave_email: str | None = None,
        do1_email: str | None = None,
        do2_email: str | None = None,
        ds_email: str | None = None,
        use_in_memory_cache: bool = True,
    ) -> tuple[
        "SyftEnclaveClient",
        "SyftEnclaveClient",
        "SyftEnclaveClient",
        "SyftEnclaveClient",
    ]:
        """Create 4 interconnected clients for testing enclave scenarios.

        Peer topology:
        - Enclave: peers with DO1, DO2, DS
        - DO1: peers with DS, Enclave (not DO2)
        - DO2: peers with DS, Enclave (not DO1)
        - DS: peers with DO1, DO2, Enclave

        Returns:
            Tuple of (enclave, do1, do2, ds)
        """
        configs = create_configs(
            enclave_email, do1_email, do2_email, ds_email, use_in_memory_cache
        )
        managers = create_managers(configs)
        setup_connections(managers)
        setup_callbacks(managers)
        write_versions(managers)
        wire_peers(managers)

        return tuple(cls(m) for m in managers)
