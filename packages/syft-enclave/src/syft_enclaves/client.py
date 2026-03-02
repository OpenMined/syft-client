from syft_client.sync.syftbox_manager import SyftboxManager, SyftboxManagerConfig
from syft_client.sync.connections.drive.mock_drive_service import (
    MockDriveBackingStore,
    MockDriveService,
)
from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection
from syft_client.sync.peers.peer import Peer
from syft_client.sync.peers.peer_list import PeerList


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

    def add_peer_as_do(
        self, peer_email: str, force: bool = False, verbose: bool = True
    ):
        self._manager.add_peer_as_do(peer_email, force=force, verbose=verbose)

    def add_peer_as_ds(
        self, peer_email: str, force: bool = False, verbose: bool = True
    ):
        self._manager.add_peer_as_ds(peer_email, force=force, verbose=verbose)

    def load_peers(self):
        self._manager.load_peers()

    def load_peers_as_do(self):
        self._manager.load_peers_as_do()

    def load_peers_as_ds(self):
        self._manager.load_peers_as_ds()

    def approve_peer_request(
        self,
        email_or_peer: str | Peer,
        verbose: bool = True,
        peer_must_exist: bool = True,
    ):
        self._manager.approve_peer_request(
            email_or_peer, verbose=verbose, peer_must_exist=peer_must_exist
        )

    def approve_peer_request_as_do(
        self,
        email_or_peer: str | Peer,
        verbose: bool = True,
        peer_must_exist: bool = True,
    ):
        self._manager.approve_peer_request_as_do(
            email_or_peer, verbose=verbose, peer_must_exist=peer_must_exist
        )

    def reject_peer_request(self, email_or_peer: str | Peer):
        self._manager.reject_peer_request(email_or_peer)

    def reject_peer_request_as_do(self, email_or_peer: str | Peer):
        self._manager.reject_peer_request_as_do(email_or_peer)

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
        configs = _create_configs(
            enclave_email, do1_email, do2_email, ds_email, use_in_memory_cache
        )
        managers = _create_managers(configs)
        _setup_connections(managers)
        _setup_callbacks(managers)
        _write_versions(managers)
        _wire_peers(managers)

        return tuple(cls(m) for m in managers)


def _create_configs(
    enclave_email, do1_email, do2_email, ds_email, use_in_memory_cache
) -> tuple:
    enclave_config = SyftboxManagerConfig._base_config_for_testing(
        email=enclave_email,
        has_do_role=True,
        use_in_memory_cache=use_in_memory_cache,
    )
    do1_config = SyftboxManagerConfig._base_config_for_testing(
        email=do1_email,
        has_do_role=True,
        use_in_memory_cache=use_in_memory_cache,
    )
    do2_config = SyftboxManagerConfig._base_config_for_testing(
        email=do2_email,
        has_do_role=True,
        use_in_memory_cache=use_in_memory_cache,
    )
    ds_config = SyftboxManagerConfig._base_config_for_testing(
        email=ds_email,
        has_ds_role=True,
        use_in_memory_cache=use_in_memory_cache,
    )
    return enclave_config, do1_config, do2_config, ds_config


def _create_managers(configs) -> tuple:
    return tuple(SyftboxManager.from_config(c) for c in configs)


def _setup_connections(managers: tuple):
    enclave, do1, do2, ds = managers
    backing_store = MockDriveBackingStore()

    for manager in managers:
        service = MockDriveService(backing_store, manager.email)
        connection = GDriveConnection.from_service(manager.email, service)
        manager._add_connection(connection)


def _setup_callbacks(managers: tuple):
    enclave, do1, do2, ds = managers

    # DS file writer callback
    ds.file_writer.add_callback(
        "write_file",
        ds.datasite_watcher_syncer.on_file_change,
    )

    # DO event cache callbacks for job handling
    for do_manager in (enclave, do1, do2):
        do_manager.datasite_owner_syncer.event_cache.add_callback(
            "on_event_local_write",
            do_manager.job_file_change_handler._handle_file_change,
        )


def _write_versions(managers: tuple):
    for manager in managers:
        manager.version_manager.write_own_version()


def _wire_peers(managers: tuple):
    enclave, do1, do2, ds = managers

    # DS requests peering with all DOs
    ds.add_peer(enclave.email)
    ds.add_peer(do1.email)
    ds.add_peer(do2.email)

    # DOs load and approve DS peer requests
    for do_manager in (enclave, do1, do2):
        do_manager.load_peers()
        do_manager.approve_peer_request(ds.email)

    # DO-to-DO peering (auto-approves since both are DOs)
    enclave.add_peer(do1.email)
    enclave.add_peer(do2.email)
    do1.add_peer(enclave.email)
    do2.add_peer(enclave.email)
