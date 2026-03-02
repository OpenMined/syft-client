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


def write_versions(managers: tuple):
    for manager in managers:
        manager.version_manager.write_own_version()


def wire_peers(managers: tuple):
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
