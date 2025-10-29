from syft_process_manager import ProcessHandle, ProcessManager
from syft_process_manager.managed_process.launcher import create_handle_for_function

from syft_client.syncv2.syftbox_manager import SyftboxManager, SyftboxManagerConfig


def run_manager(
    config: SyftboxManagerConfig,
) -> SyftboxManager:
    print("Using config:")
    print(config.model_dump_json(indent=2))
    print()
    manager = SyftboxManager.from_config(config)
    manager.run_forever()


def get_or_create_syftbox_manager_handle(
    config: SyftboxManagerConfig,
    name: str = "syftbox_manager",
    env: dict | None = None,
    ttl_seconds: int | None = None,
    log_level: str = "INFO",
    process_manager: ProcessManager | None = None,
    overwrite_existing: bool = False,
) -> ProcessHandle:
    process_manager = process_manager or ProcessManager()
    if not overwrite_existing:
        existing_handle = process_manager.get(name)
        if existing_handle is not None:
            return existing_handle

    # Alternative: create + run = syft_process_manager.run_function(**same_args)
    return create_handle_for_function(
        run_manager,
        config,
        name=name,
        env=env,
        ttl_seconds=ttl_seconds,
        log_level=log_level,
        process_manager=process_manager,
        overwrite=overwrite_existing,
    )


def run_syftbox_manager_in_process(
    config: SyftboxManagerConfig,
    name: str = "syftbox_manager",
    env: dict | None = None,
    ttl_seconds: int | None = None,
    log_level: str = "INFO",
    process_manager: ProcessManager | None = None,
    overwrite_existing: bool = False,
) -> SyftboxManager:
    handle = get_or_create_syftbox_manager_handle(
        config=config,
        name=name,
        env=env,
        ttl_seconds=ttl_seconds,
        log_level=log_level,
        process_manager=process_manager,
        overwrite_existing=overwrite_existing,
    )
    try:
        handle.start()
    except RuntimeError as e:
        print(f"Error starting SyftboxManager: {e}")
    return handle
