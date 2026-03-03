from syft_client.sync.syftbox_manager import SyftboxManager, SyftboxManagerConfig
from syft_client.sync.connections.drive.mock_drive_service import (
    MockDriveBackingStore,
    MockDriveService,
)
from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection


def create_configs(
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
        has_ds_role=True,
        use_in_memory_cache=use_in_memory_cache,
    )
    do2_config = SyftboxManagerConfig._base_config_for_testing(
        email=do2_email,
        has_do_role=True,
        has_ds_role=True,
        use_in_memory_cache=use_in_memory_cache,
    )
    ds_config = SyftboxManagerConfig._base_config_for_testing(
        email=ds_email,
        has_ds_role=True,
        use_in_memory_cache=use_in_memory_cache,
    )
    return enclave_config, do1_config, do2_config, ds_config


def create_managers(configs) -> tuple:
    return tuple(SyftboxManager.from_config(c) for c in configs)


def setup_connections(managers: tuple):
    backing_store = MockDriveBackingStore()

    for manager in managers:
        service = MockDriveService(backing_store, manager.email)
        connection = GDriveConnection.from_service(manager.email, service)
        manager._add_connection(connection)


def setup_callbacks(managers: tuple):
    enclave, do1, do2, ds = managers

    # DS file writer callbacks (for all managers with DS role)
    for ds_manager in (do1, do2, ds):
        ds_manager.file_writer.add_callback(
            "write_file",
            ds_manager.datasite_watcher_syncer.on_file_change,
        )

    # DO event cache callbacks for job handling
    for do_manager in (enclave, do1, do2):
        do_manager.datasite_owner_syncer.event_cache.add_callback(
            "on_event_local_write",
            do_manager.job_file_change_handler._handle_file_change,
        )


def write_versions(managers: tuple):
    for manager in managers:
        manager.version_manager.write_own_version()


def wire_peers(managers: tuple):
    enclave, do1, do2, ds = managers

    # DS requests peering with DO1, DO2, and enclave
    ds.add_peer_as_ds(do1.email)
    ds.add_peer_as_ds(do2.email)
    ds.add_peer_as_ds(enclave.email)

    # DO1 and DO2: load incoming DS request, approve it, then request peering with enclave
    for dual_manager in (do1, do2):
        dual_manager.load_peers_as_do()
        dual_manager.approve_peer_request_as_do(ds.email)
        dual_manager.add_peer_as_ds(enclave.email)

    # Enclave: load all incoming requests (DS, DO1, DO2) and approve them
    enclave.load_peers_as_do()
    enclave.approve_peer_request_as_do(ds.email)
    enclave.approve_peer_request_as_do(do1.email)
    enclave.approve_peer_request_as_do(do2.email)
