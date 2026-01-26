from pathlib import Path
import copy
import warnings
from syft_client.utils import resolve_path
from concurrent.futures import ThreadPoolExecutor
import time
from pydantic import ConfigDict
from syft_job.client import JobClient, JobsList
from syft_job.job_runner import SyftJobRunner
from syft_job import SyftJobConfig
from syft_datasets.config import SyftBoxConfig
from syft_datasets.dataset_manager import SyftDatasetManager
from syft_client.sync.platforms.base_platform import BasePlatform
from pydantic import BaseModel, PrivateAttr
from typing import List, cast
from syft_client.sync.sync.caches.datasite_watcher_cache import (
    DataSiteWatcherCacheConfig,
)
from syft_client.sync.sync.caches.datasite_owner_cache import (
    DataSiteOwnerEventCacheConfig,
)
from syft_client.sync.peers.peer_list import PeerList
from syft_client.sync.peers.peer import Peer, PeerState
from syft_client.sync.connections.base_connection import (
    SyftboxPlatformConnection,
)
from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.utils.syftbox_utils import (
    random_email,
    random_syftbox_folder_for_testing,
)
from syft_client.sync.file_writer import FileWriter

from syft_client.sync.job_file_change_handler import JobFileChangeHandler
from syft_client.sync.connections.connection_router import ConnectionRouter

from syft_client.sync.connections.drive.grdrive_config import GdriveConnectionConfig
from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection
from syft_client.sync.connections.drive.mock_drive_service import (
    MockDriveBackingStore,
    MockDriveService,
)
from syft_client.sync.connections.inmemory_connection import (
    InMemoryPlatformConnection,
)
from syft_client.sync.sync.datasite_owner_syncer import (
    DatasiteOwnerSyncer,
    DatasiteOwnerSyncerConfig,
)
from syft_client.sync.sync.datasite_watcher_syncer import (
    DatasiteWatcherSyncer,
    DatasiteWatcherSyncerConfig,
)
from syft_client.sync.version.version_manager import (
    VersionManager,
    VersionManagerConfig,
)
import os

COLAB_DEFAULT_SYFTBOX_FOLDER = Path("/")
JUPYTER_DEFAULT_SYFTBOX_FOLDER = Path.home() / "SyftBox"
COLLECTION_SUBPATH = Path("public/syft_datasets")


def get_jupyter_default_syftbox_folder(email: str):
    return Path.home() / f"SyftBox_{email}"


def get_colab_default_syftbox_folder(email: str):
    return Path("/content") / f"SyftBox_{email}"


class SyftboxManagerConfig(BaseModel):
    email: str
    syftbox_folder: Path
    write_files: bool = True
    only_ds: bool = False
    only_datasite_owner: bool = False
    use_in_memory_cache: bool = True

    datasite_owner_syncer_config: DatasiteOwnerSyncerConfig
    version_manager_config: VersionManagerConfig

    datasite_watcher_syncer_config: DatasiteWatcherSyncerConfig
    dataset_manager_config: SyftBoxConfig
    job_client_config: SyftJobConfig

    @classmethod
    def for_colab(
        cls, email: str, only_ds: bool = False, only_datasite_owner: bool = False
    ):
        if not only_ds and not only_datasite_owner:
            raise ValueError(
                "At least one of only_ds or only_datasite_owner must be True"
            )

        syftbox_folder = get_colab_default_syftbox_folder(email)
        use_in_memory_cache = False
        collections_folder = syftbox_folder / email / COLLECTION_SUBPATH
        connection_configs = [GdriveConnectionConfig(email=email, token_path=None)]
        datasite_owner_syncer_config = DatasiteOwnerSyncerConfig(
            email=email,
            syftbox_folder=syftbox_folder,
            collections_folder=collections_folder,
            connection_configs=connection_configs,
            cache_config=DataSiteOwnerEventCacheConfig(
                email=email,
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
                collections_folder=collections_folder,
            ),
        )
        datasite_watcher_syncer_config = DatasiteWatcherSyncerConfig(
            syftbox_folder=syftbox_folder,
            email=email,
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
                collection_subpath=COLLECTION_SUBPATH,
                connection_configs=connection_configs,
            ),
        )
        job_client_config = SyftJobConfig(
            syftbox_folder=syftbox_folder,
            email=email,
        )
        dataset_manager_config = SyftBoxConfig(
            syftbox_folder=syftbox_folder,
            email=email,
        )
        version_manager_config = VersionManagerConfig(
            connection_configs=connection_configs,
            is_do=only_datasite_owner,
        )
        return cls(
            email=email,
            syftbox_folder=syftbox_folder,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            connection_configs=connection_configs,
            use_in_memory_cache=False,
            datasite_owner_syncer_config=datasite_owner_syncer_config,
            datasite_watcher_syncer_config=datasite_watcher_syncer_config,
            dataset_manager_config=dataset_manager_config,
            job_client_config=job_client_config,
            version_manager_config=version_manager_config,
        )

    @classmethod
    def for_jupyter(
        cls,
        email: str,
        only_ds: bool = False,
        only_datasite_owner: bool = False,
        token_path: Path | None = None,
    ):
        if not only_ds and not only_datasite_owner:
            raise ValueError(
                "At least one of only_ds or only_datasite_owner must be True"
            )

        syftbox_folder = get_jupyter_default_syftbox_folder(email)
        collections_folder = syftbox_folder / email / COLLECTION_SUBPATH

        connection_configs = [
            GdriveConnectionConfig(email=email, token_path=token_path)
        ]
        datasite_owner_syncer_config = DatasiteOwnerSyncerConfig(
            email=email,
            syftbox_folder=syftbox_folder,
            collections_folder=collections_folder,
            connection_configs=connection_configs,
            cache_config=DataSiteOwnerEventCacheConfig(
                email=email,
                use_in_memory_cache=False,
                syftbox_folder=syftbox_folder,
                collections_folder=collections_folder,
                connection_configs=connection_configs,
            ),
        )
        datasite_watcher_syncer_config = DatasiteWatcherSyncerConfig(
            syftbox_folder=syftbox_folder,
            email=email,
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=False,
                syftbox_folder=syftbox_folder,
                collection_subpath=COLLECTION_SUBPATH,
                connection_configs=connection_configs,
            ),
        )
        dataset_manager_config = SyftBoxConfig(
            syftbox_folder=syftbox_folder,
            email=email,
        )
        job_client_config = SyftJobConfig(
            syftbox_folder=syftbox_folder,
            email=email,
        )
        version_manager_config = VersionManagerConfig(
            connection_configs=connection_configs,
            is_do=only_datasite_owner,
        )
        return cls(
            email=email,
            syftbox_folder=syftbox_folder,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            use_in_memory_cache=False,
            datasite_owner_syncer_config=datasite_owner_syncer_config,
            datasite_watcher_syncer_config=datasite_watcher_syncer_config,
            dataset_manager_config=dataset_manager_config,
            job_client_config=job_client_config,
            version_manager_config=version_manager_config,
        )

    @classmethod
    def base_config_for_in_memory_connection(
        cls,
        email: str | None = None,
        syftbox_folder: Path | None = None,
        write_files: bool = False,
        only_ds: bool = False,
        only_datasite_owner: bool = False,
        use_in_memory_cache: bool = True,
        check_versions: bool = False,
    ):
        syftbox_folder = syftbox_folder or random_syftbox_folder_for_testing()
        email = email or random_email()
        collections_folder = syftbox_folder / email / COLLECTION_SUBPATH

        datasite_owner_syncer_config = DatasiteOwnerSyncerConfig(
            email=email,
            syftbox_folder=syftbox_folder,
            collections_folder=collections_folder,
            write_files=write_files,
            cache_config=DataSiteOwnerEventCacheConfig(
                email=email,
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
                collections_folder=collections_folder,
            ),
        )
        datasite_watcher_syncer_config = DatasiteWatcherSyncerConfig(
            email=email,
            syftbox_folder=syftbox_folder,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
                collection_subpath=COLLECTION_SUBPATH,
            ),
        )

        dataset_manager_config = SyftBoxConfig(
            syftbox_folder=syftbox_folder,
            email=email,
        )
        job_client_config = SyftJobConfig(
            syftbox_folder=Path(syftbox_folder),
            email=email,
        )
        version_manager_config = VersionManagerConfig(
            connection_configs=[],  # Empty for in-memory, connections added later
            n_threads=2,  # Use fewer threads for testing
            ignore_protocol_version=not check_versions,
            ignore_client_version=not check_versions,
            is_do=only_datasite_owner,
        )

        return cls(
            email=email,
            syftbox_folder=syftbox_folder,
            write_files=write_files,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            use_in_memory_cache=use_in_memory_cache,
            datasite_owner_syncer_config=datasite_owner_syncer_config,
            datasite_watcher_syncer_config=datasite_watcher_syncer_config,
            dataset_manager_config=dataset_manager_config,
            job_client_config=job_client_config,
            version_manager_config=version_manager_config,
        )

    @classmethod
    def for_google_drive_testing_connection(
        cls,
        email: str,
        token_path: Path,
        syftbox_folder: str | None = None,
        write_files: bool = False,
        only_ds: bool = False,
        only_datasite_owner: bool = False,
        use_in_memory_cache: bool = True,
        check_versions: bool = False,
    ):
        syftbox_folder = syftbox_folder or random_syftbox_folder_for_testing()
        email = email or random_email()
        collections_folder = Path(syftbox_folder) / email / COLLECTION_SUBPATH
        connection_configs = [
            GdriveConnectionConfig(email=email, token_path=token_path)
        ]
        datasite_owner_syncer_config = DatasiteOwnerSyncerConfig(
            email=email,
            syftbox_folder=syftbox_folder,
            collections_folder=collections_folder,
            connection_configs=connection_configs,
            cache_config=DataSiteOwnerEventCacheConfig(
                email=email,
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
                collections_folder=collections_folder,
            ),
        )
        datasite_watcher_syncer_config = DatasiteWatcherSyncerConfig(
            syftbox_folder=syftbox_folder,
            email=email,
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
                collection_subpath=COLLECTION_SUBPATH,
                connection_configs=connection_configs,
            ),
        )

        dataset_manager_config = SyftBoxConfig(
            syftbox_folder=syftbox_folder,
            email=email,
        )
        job_client_config = SyftJobConfig(
            syftbox_folder=syftbox_folder,
            email=email,
        )
        version_manager_config = VersionManagerConfig(
            connection_configs=connection_configs,
            ignore_protocol_version=not check_versions,
            ignore_client_version=not check_versions,
            is_do=only_datasite_owner,
        )
        return cls(
            email=email,
            syftbox_folder=syftbox_folder,
            write_files=write_files,
            datasite_owner_syncer_config=datasite_owner_syncer_config,
            datasite_watcher_syncer_config=datasite_watcher_syncer_config,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            use_in_memory_cache=False,
            dataset_manager_config=dataset_manager_config,
            job_client_config=job_client_config,
            version_manager_config=version_manager_config,
        )


class SyftboxManager(BaseModel):
    # needed for peers
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_writer: FileWriter
    syftbox_folder: Path
    email: str
    dev_mode: bool = False
    datasite_watcher_syncer: DatasiteWatcherSyncer | None = None

    datasite_owner_syncer: DatasiteOwnerSyncer | None = None
    job_file_change_handler: JobFileChangeHandler | None = None
    dataset_manager: SyftDatasetManager | None = None
    job_client: JobClient | None = None
    job_runner: SyftJobRunner | None = None
    version_manager: VersionManager | None = None

    _executor: ThreadPoolExecutor = PrivateAttr(
        default_factory=lambda: ThreadPoolExecutor(max_workers=10)
    )

    @property
    def peers(self) -> PeerList:
        """
        Get the combined list of peers (approved + requests).
        Automatically calls sync() before returning peers
        if PRE_SYNC environment variable is set to "true" (case-insensitive).

        PRE_SYNC defaults to "true", so auto-sync is enabled by default.
        To disable auto-sync, set: PRE_SYNC=false

        Returns PeerList with approved peers first, then requests.
        """
        if os.environ.get("PRE_SYNC", "true").lower() == "true":
            self.sync()

        if self.is_do:
            combined = PeerList(
                self.version_manager.approved_peers + self.version_manager.pending_peers
            )
        else:
            peers = copy.deepcopy(self.version_manager.outstanding_peers)
            for peer in peers:
                peer.state = PeerState.ACCEPTED
            combined = PeerList(peers)

        return combined

    @classmethod
    def from_config(cls, config: SyftboxManagerConfig):
        file_writer = FileWriter(
            base_path=config.syftbox_folder, write_files=config.write_files
        )

        datasite_owner_syncer = None
        job_file_change_handler = None
        datasite_watcher_syncer = None
        job_runner = None

        dataset_manager = SyftDatasetManager.from_config(config.dataset_manager_config)
        job_client = JobClient.from_config(config.job_client_config)

        if config.only_datasite_owner:
            datasite_owner_syncer = DatasiteOwnerSyncer.from_config(
                config.datasite_owner_syncer_config
            )

            job_file_change_handler = JobFileChangeHandler()
            job_runner = SyftJobRunner.from_config(config.job_client_config)

        if not config.only_datasite_owner:
            datasite_watcher_syncer = DatasiteWatcherSyncer.from_config(
                config.datasite_watcher_syncer_config
            )

        version_manager = VersionManager.from_config(config.version_manager_config)

        manager_res = cls(
            syftbox_folder=config.syftbox_folder,
            email=config.email,
            file_writer=file_writer,
            datasite_owner_syncer=datasite_owner_syncer,
            job_file_change_handler=job_file_change_handler,
            datasite_watcher_syncer=datasite_watcher_syncer,
            dataset_manager=dataset_manager,
            job_client=job_client,
            job_runner=job_runner,
            version_manager=version_manager,
        )

        return manager_res

    @classmethod
    def for_colab(
        cls, email: str, only_ds: bool = False, only_datasite_owner: bool = False
    ):
        manager = cls.from_config(
            SyftboxManagerConfig.for_colab(
                email=email,
                only_ds=only_ds,
                only_datasite_owner=only_datasite_owner,
            )
        )
        manager.version_manager.write_own_version()
        return manager

    @classmethod
    def for_jupyter(
        cls,
        email: str,
        only_ds: bool = False,
        only_datasite_owner: bool = False,
        token_path: Path | None = None,
    ):
        if token_path is not None:
            token_path = Path(token_path)
        manager = cls.from_config(
            SyftboxManagerConfig.for_jupyter(
                email=email,
                only_ds=only_ds,
                only_datasite_owner=only_datasite_owner,
                token_path=token_path,
            )
        )
        manager.version_manager.write_own_version()
        return manager

    @classmethod
    def pair_with_google_drive_testing_connection(
        cls,
        do_email: str,
        ds_email: str,
        do_token_path: Path,
        ds_token_path: Path,
        base_path1: str | None = None,
        base_path2: str | None = None,
        add_peers: bool = True,
        load_peers: bool = False,
        use_in_memory_cache: bool = True,
        clear_caches: bool = True,
        check_versions: bool = False,
    ):
        receiver_config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=do_email,
            syftbox_folder=base_path1,
            use_in_memory_cache=use_in_memory_cache,
            token_path=do_token_path,
            only_ds=False,
            only_datasite_owner=True,
            check_versions=check_versions,
        )

        receiver_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=ds_email,
            syftbox_folder=base_path2,
            use_in_memory_cache=use_in_memory_cache,
            token_path=ds_token_path,
            only_ds=True,
            only_datasite_owner=False,
            check_versions=check_versions,
        )
        sender_manager = cls.from_config(sender_config)

        # Write version files if version checking is enabled
        if check_versions:
            sender_manager.version_manager.write_own_version()
            receiver_manager.version_manager.write_own_version()

        # this makes sure that when we write a file as sender, the inactive file watcher picks it up
        sender_manager.file_writer.add_callback(
            "write_file",
            sender_manager.datasite_watcher_syncer.on_file_change,
        )

        # this makes sure that when we receive a message, the handler is called
        # receiver_manager.proposed_file_change_puller.add_callback(
        #     "on_proposed_filechange_receive",
        #     receiver_manager.datasite_owner_syncer.handle_proposed_filechange_event,
        # )
        # this make sure that when the receiver writes a file to disk,
        # the file watcher picks it up
        # we use the underscored method to allow for monkey patching
        receiver_manager.datasite_owner_syncer.event_cache.add_callback(
            "on_event_local_write",
            receiver_manager.job_file_change_handler._handle_file_change,
        )

        if add_peers:
            # DS creates peer request
            sender_manager.add_peer(receiver_manager.email)
            # unfortunately, we need this because of delays in gdrive
            # DO approves the peer request automatically (for backward compatibility)
            receiver_manager.load_peers()
            # we are not checking if the peer exists because of delays in gdrive
            receiver_manager.approve_peer_request(
                sender_manager.email, peer_must_exist=False
            )
        if load_peers:
            receiver_manager.load_peers()
            sender_manager.load_peers()

        if clear_caches:
            receiver_manager.clear_caches()
            sender_manager.clear_caches()

        # create inbox folder
        return sender_manager, receiver_manager

    @classmethod
    def pair_with_in_memory_connection(
        cls,
        email1: str | None = None,
        email2: str | None = None,
        base_path1: str | None = None,
        base_path2: str | None = None,
        sync_automatically: bool = True,
        add_peers: bool = True,
        use_in_memory_cache: bool = True,
        check_versions: bool = False,
    ):
        # this doesnt contain the connections, as we need to set them after creation
        receiver_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email1,
            syftbox_folder=base_path1,
            only_ds=False,
            only_datasite_owner=True,
            use_in_memory_cache=use_in_memory_cache,
            check_versions=check_versions,
        )

        do_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email2,
            syftbox_folder=base_path2,
            only_ds=True,
            only_datasite_owner=False,
            use_in_memory_cache=use_in_memory_cache,
            check_versions=check_versions,
        )
        ds_manager = cls.from_config(sender_config)

        # this makes sure that when we write a file as sender, the inactive file watcher picks it up
        ds_manager.file_writer.add_callback(
            "write_file",
            ds_manager.datasite_watcher_syncer.on_file_change,
        )
        # this makes sure that a message travels from through our in memory platform from pusher to puller

        if sync_automatically:
            receiver_receive_function = do_manager.sync
        else:
            receiver_receive_function = None

        sender_in_memory_connection = InMemoryPlatformConnection(
            receiver_function=receiver_receive_function,
            owner_email=ds_manager.email,
        )
        ds_manager.add_connection(sender_in_memory_connection)

        # this make sure we can do communication the other way, it also makes sure we have a fake backing store for the receiver
        # so we can store events in memory
        # we also make sure we write to the same backing store so we get consistent state
        # sender_receiver_function = (
        #     sender_manager.proposed_file_change_handler.on_proposed_filechange_receive
        # )
        def sender_receiver_function(*args, **kwargs):
            pass

        sender_backing_store = ds_manager.datasite_watcher_syncer.connection_router.connection_for_eventlog().backing_store
        receiver_connection = InMemoryPlatformConnection(
            receiver_function=sender_receiver_function,
            backing_store=sender_backing_store,
            owner_email=do_manager.email,
        )
        do_manager.add_connection(receiver_connection)

        # Write version files after connections are set up
        ds_manager.version_manager.write_own_version()
        do_manager.version_manager.write_own_version()

        # this make sure that when the receiver writes a file to disk,
        # the file watcher picks it up
        # we use the underscored method to allow for monkey patching
        do_manager.datasite_owner_syncer.event_cache.add_callback(
            "on_event_local_write",
            do_manager.job_file_change_handler._handle_file_change,
        )

        if add_peers:
            # DS creates peer request
            ds_manager.add_peer(do_manager.email)
            # DO approves the peer request automatically (for backward compatibility)
            do_manager.load_peers()
            do_manager.approve_peer_request(ds_manager.email)

        return ds_manager, do_manager

    @classmethod
    def pair_with_mock_drive_service_connection(
        cls,
        email1: str | None = None,
        email2: str | None = None,
        base_path1: str | None = None,
        base_path2: str | None = None,
        sync_automatically: bool = True,
        add_peers: bool = True,
        use_in_memory_cache: bool = True,
        check_versions: bool = False,
    ):
        """Create a pair of managers using mock Google Drive services for testing.

        This creates managers that use the actual GDriveConnection code but with
        mock services instead of real Google Drive API calls. This allows testing
        the full GDrive code path without network calls.

        Args:
            email1: Email for the DO manager (defaults to random)
            email2: Email for the DS manager (defaults to random)
            base_path1: Base path for DO manager (defaults to temp dir)
            base_path2: Base path for DS manager (defaults to temp dir)
            sync_automatically: Whether to sync when DS sends changes
            add_peers: Whether to automatically add and approve peers
            use_in_memory_cache: Whether to use in-memory caches
            check_versions: Whether to check protocol/client versions

        Returns:
            Tuple of (ds_manager, do_manager)
        """
        # Create configs using the existing base config generator
        do_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email1,
            syftbox_folder=base_path1,
            only_ds=False,
            only_datasite_owner=True,
            use_in_memory_cache=use_in_memory_cache,
            check_versions=check_versions,
        )

        ds_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email2,
            syftbox_folder=base_path2,
            only_ds=True,
            only_datasite_owner=False,
            use_in_memory_cache=use_in_memory_cache,
            check_versions=check_versions,
        )

        # Create managers from configs
        do_manager = cls.from_config(do_config)
        ds_manager = cls.from_config(ds_config)

        # Create shared backing store for mock services
        shared_backing_store = MockDriveBackingStore()

        # Create mock services (share same backing store, different current_user)
        do_mock_service = MockDriveService(shared_backing_store, do_manager.email)
        ds_mock_service = MockDriveService(shared_backing_store, ds_manager.email)

        # Create GDriveConnection instances with mock services
        do_connection = GDriveConnection.from_mock_service(
            do_manager.email, do_mock_service
        )
        ds_connection = GDriveConnection.from_mock_service(
            ds_manager.email, ds_mock_service
        )

        # Add connections to managers
        # For DO: add connection to datasite_owner_syncer and version_manager
        do_manager.datasite_owner_syncer.connection_router.add_connection(do_connection)
        do_manager.version_manager.connection_router.add_connection(do_connection)

        # For DS: add connection to datasite_watcher_syncer and version_manager
        ds_manager.datasite_watcher_syncer.connection_router.add_connection(
            ds_connection
        )
        ds_manager.datasite_watcher_syncer.datasite_watcher_cache.connection_router.add_connection(
            ds_connection
        )
        ds_manager.version_manager.connection_router.add_connection(ds_connection)

        # Set up callbacks for DS -> DO communication
        ds_manager.file_writer.add_callback(
            "write_file",
            ds_manager.datasite_watcher_syncer.on_file_change,
        )

        # Set up callback for DO job handling
        do_manager.datasite_owner_syncer.event_cache.add_callback(
            "on_event_local_write",
            do_manager.job_file_change_handler._handle_file_change,
        )

        # Write version files
        ds_manager.version_manager.write_own_version()
        do_manager.version_manager.write_own_version()

        if add_peers:
            # DS creates peer request
            ds_manager.add_peer(do_manager.email)
            # DO approves the peer request
            do_manager.load_peers()
            do_manager.approve_peer_request(ds_manager.email)

        return ds_manager, do_manager

    def add_peer(self, peer_email: str, force: bool = False, verbose: bool = True):
        """Add a peer. Delegates to VersionManager."""
        self.version_manager.add_peer(peer_email, force=force, verbose=verbose)

    def submit_bash_job(
        self, user: str, *args, sync=True, force_submission: bool = False, **kwargs
    ):
        # Check version compatibility before submission (uses cached versions)
        if not force_submission:
            self.version_manager.check_version_for_submission(user, force=False)
        job_dir = self.job_client.submit_bash_job(user, *args, **kwargs)
        self.push_job_files(job_dir)

    def submit_python_job(
        self, user: str, *args, sync=True, force_submission: bool = False, **kwargs
    ):
        # Check version compatibility before submission (uses cached versions)
        if not force_submission:
            self.version_manager.check_version_for_submission(user, force=False)
        job_dir = self.job_client.submit_python_job(user, *args, **kwargs)
        self.push_job_files(job_dir)
        print(f"Submitted python job, job files are in {job_dir}")

    def push_job_files(self, job_dir: Path):
        file_paths = [Path(p) for p in job_dir.rglob("*") if p.is_file()]
        relative_file_paths = [p.relative_to(self.syftbox_folder) for p in file_paths]

        last_file = False
        for i, relative_file_path in enumerate(relative_file_paths):
            # only send a message for the last file, so we reduce the number of messages sent
            if i == len(relative_file_paths) - 1:
                last_file = True

            self.datasite_watcher_syncer.on_file_change(
                relative_file_path, process_now=last_file
            )

    @property
    def is_do(self) -> bool:
        return self.datasite_owner_syncer is not None

    def sync(self):
        self.load_peers()
        if self.is_do:
            peer_emails = [peer.email for peer in self.version_manager.approved_peers]
            # Filter to compatible peers using cached versions, warn for incompatible
            compatible_emails = self.version_manager.get_compatible_peer_emails(
                peer_emails, warn_incompatible=True
            )
            self.datasite_owner_syncer.sync(compatible_emails)
        else:
            # ds
            peer_emails = [
                peer.email for peer in self.version_manager.outstanding_peers
            ]
            # Warn if all connected peers are incompatible (uses cached versions)
            self.version_manager.warn_if_all_peers_incompatible(peer_emails)
            self.datasite_watcher_syncer.sync_down(peer_emails)

    def load_peers(self):
        """Load peers from connection router. Delegates to VersionManager."""
        cast(VersionManager, self.version_manager).load_peers()

    def check_peer_request_exists(self, email: str) -> bool:
        """Check if a peer request exists. Delegates to VersionManager."""
        return self.version_manager.check_peer_request_exists(email)

    def approve_peer_request(
        self,
        email_or_peer: str | Peer,
        verbose: bool = True,
        peer_must_exist: bool = True,
    ):
        """Approve a pending peer request. Delegates to VersionManager."""
        self.version_manager.approve_peer_request(
            email_or_peer, verbose=verbose, peer_must_exist=peer_must_exist
        )

        # Share all "any" datasets with the new peer so they can discover them
        # (Google Drive "anyone with link" files are not discoverable via search)
        email = email_or_peer if isinstance(email_or_peer, str) else email_or_peer.email
        self._share_any_datasets_with_peer(email)

    def _share_any_datasets_with_peer(self, peer_email: str):
        """Share all datasets that have 'any' permission with a specific peer.

        This is needed because Google Drive "anyone with link" files are not
        discoverable via search. By adding explicit user sharing, the peer
        can discover these datasets.

        Uses cache populated during pull_initial_state() in DatasiteOwnerSyncer.
        """
        for tag, content_hash in self.datasite_owner_syncer._any_shared_datasets:
            try:
                self.connection_router.share_dataset_collection(
                    tag, content_hash, peer_email
                )
            except Exception:
                # Ignore errors (e.g., already shared)
                pass

    def reject_peer_request(self, email_or_peer: str | Peer):
        """Reject a pending peer request. Delegates to VersionManager."""
        self.version_manager.reject_peer_request(email_or_peer)

    @property
    def jobs(self) -> JobsList:
        """
        Get the list of jobs. Automatically calls sync() before returning jobs
        if PRE_SYNC environment variable is set to "true" (case-insensitive).

        PRE_SYNC defaults to "true", so auto-sync is enabled by default.
        To disable auto-sync, set: PRE_SYNC=false
        """
        if os.environ.get("PRE_SYNC", "true").lower() == "true":
            self.sync()
        return self.job_client.jobs

    def process_approved_jobs(
        self,
        stream_output: bool = True,
        timeout: int | None = None,
        force_execution: bool = False,
    ) -> None:
        """
        Process approved jobs. Automatically calls sync() after processing

        Args:
            stream_output: If True (default), stream output in real-time.
                        If False, capture output at end.
            timeout: Timeout in seconds per job. Defaults to 300 (5 minutes).
                    Can also be set via SYFT_JOB_TIMEOUT_SECONDS env var.
            force_execution: If True, process all approved jobs regardless of
                           version compatibility. If False (default), skip jobs
                           from peers with incompatible or unknown versions.

        PRE_SYNC defaults to "true", so auto-sync is enabled by default.
        To disable auto-sync, set: PRE_SYNC=false
        """
        skip_job_names = []

        if not force_execution:
            # Check version compatibility for all approved job submitters (uses cached versions)
            approved_jobs = [
                job for job in self.job_client.jobs if job.status == "approved"
            ]

            for job in approved_jobs:
                if job.submitted_by == "unknown":
                    continue

                if not self.version_manager.is_peer_version_compatible(
                    job.submitted_by
                ):
                    # Warn about incompatible job
                    peer_version = self.version_manager.get_peer_version(
                        job.submitted_by
                    )
                    if peer_version is None:
                        warnings.warn(
                            f"Skipping job '{job.name}' from {job.submitted_by}: "
                            "version unknown. Use force_execution=True to override."
                        )
                    else:
                        own_version = self.version_manager.get_own_version()
                        reason = own_version.get_incompatibility_reason(peer_version)
                        warnings.warn(
                            f"Skipping job '{job.name}' from {job.submitted_by}: "
                            f"{reason}. Use force_execution=True to override."
                        )
                    skip_job_names.append(job.name)

        self.job_runner.process_approved_jobs(
            stream_output=stream_output,
            timeout=timeout,
            skip_job_names=skip_job_names if skip_job_names else None,
        )

        if os.environ.get("PRE_SYNC", "true").lower() == "true":
            self.sync()

    def add_connection(self, connection: SyftboxPlatformConnection):
        # all connection routers are pointers to the same object for in memory setup
        if not isinstance(connection, InMemoryPlatformConnection):
            raise ValueError(
                "Only InMemoryPlatformConnections can be added to the manager"
            )

        if self.datasite_owner_syncer is not None:
            self.datasite_owner_syncer.connection_router.add_connection(connection)
        if self.datasite_watcher_syncer is not None:
            self.datasite_watcher_syncer.connection_router.add_connection(connection)
            self.datasite_watcher_syncer.datasite_watcher_cache.connection_router.add_connection(
                connection
            )

        # Add connection to version manager's router
        self.version_manager.connection_router.add_connection(connection)

    def send_file_change(self, path: str | Path, content: str):
        self.file_writer.write_file(path, content)

    def get_all_accepted_events_do(self) -> List[FileChangeEvent]:
        return self.datasite_owner_syncer.connection_router.get_all_accepted_events_messages_do()

    def create_dataset(
        self, *args, users: list[str] | str | None = None, sync=True, **kwargs
    ):
        if self.dataset_manager is None:
            raise ValueError("Dataset manager is not set")

        # Only DO can create datasets
        if not self.is_do:
            raise ValueError("Only dataset owners can create datasets")

        # Convert None to empty list
        if users is None:
            users = []

        # Create dataset locally
        dataset = self.dataset_manager.create(*args, users=users, **kwargs)

        # Upload to collection folder
        self._upload_dataset_to_collection(dataset, users)

        if sync:
            self.sync()

        return dataset

    def _upload_dataset_to_collection(self, dataset, users: list[str] | str):
        """Upload dataset files to collection folder."""
        from syft_client.sync.connections.drive.gdrive_transport import (
            DatasetCollectionFolder,
        )

        collection_tag = dataset.name

        # Prepare files to upload
        files = {}
        for mock_file in dataset.mock_files:
            if mock_file.exists():
                files[mock_file.name] = mock_file.read_bytes()

        metadata_path = dataset.mock_dir / "dataset.yaml"
        if metadata_path.exists():
            files["dataset.yaml"] = metadata_path.read_bytes()

        if dataset.readme_path and dataset.readme_path.exists():
            files[dataset.readme_path.name] = dataset.readme_path.read_bytes()

        # Compute content hash
        content_hash = DatasetCollectionFolder.compute_hash(files)

        # Create collection folder with hash in name
        self.connection_router.create_dataset_collection_folder(
            tag=collection_tag, content_hash=content_hash, owner_email=self.email
        )

        # Upload files
        self.connection_router.upload_dataset_files(collection_tag, content_hash, files)

        # Share with users
        self.connection_router.share_dataset_collection(
            collection_tag, content_hash, users
        )

        # Cache "any" datasets for quick sharing with new peers
        if users == "any":
            self.datasite_owner_syncer._any_shared_datasets.append(
                (collection_tag, content_hash)
            )

    def delete_dataset(self, *args, sync=True, **kwargs):
        if self.dataset_manager is None:
            raise ValueError("Dataset manager is not set")
        self.dataset_manager.delete(*args, **kwargs)
        if sync:
            self.sync()

    def share_dataset(self, tag: str, users: list[str] | str, sync=True):
        """
        Share an existing dataset with additional users.

        Args:
            tag: Dataset name
            users: List of email addresses or "any"
            sync: Whether to sync after sharing
        """
        from syft_client.sync.connections.drive.gdrive_transport import (
            DatasetCollectionFolder,
        )

        if self.dataset_manager is None:
            raise ValueError("Dataset manager is not set")

        if not self.is_do:
            raise ValueError("Only dataset owners can share datasets")

        # Verify dataset exists
        dataset = self.dataset_manager.get(name=tag, datasite=self.email)
        if dataset is None:
            raise ValueError(f"Dataset {tag} not found")

        # Compute current content hash from local files
        files = {}
        for mock_file in dataset.mock_files:
            if mock_file.exists():
                files[mock_file.name] = mock_file.read_bytes()
        metadata_path = dataset.mock_dir / "dataset.yaml"
        if metadata_path.exists():
            files["dataset.yaml"] = metadata_path.read_bytes()
        if dataset.readme_path and dataset.readme_path.exists():
            files[dataset.readme_path.name] = dataset.readme_path.read_bytes()

        content_hash = DatasetCollectionFolder.compute_hash(files)

        # Share collection
        self.connection_router.share_dataset_collection(tag, content_hash, users)

        if sync:
            self.sync()

    @property
    def datasets(self) -> SyftDatasetManager:
        """
        Get the dataset manager. Automatically calls sync() before returning datasets
        if PRE_SYNC environment variable is set to "true" (case-insensitive).

        PRE_SYNC defaults to "true", so auto-sync is enabled by default.
        To disable auto-sync, set: PRE_SYNC=false
        """
        if self.dataset_manager is None:
            raise ValueError("Dataset manager is not set")

        if os.environ.get("PRE_SYNC", "true").lower() == "true":
            self.sync()

        return self.dataset_manager

    @property
    def connection_router(self) -> ConnectionRouter:
        # for DOs we have a syncer, for DSs we have a watcher syncer
        if self.datasite_owner_syncer is not None:
            return self.datasite_owner_syncer.connection_router
        else:
            return self.datasite_watcher_syncer.connection_router

    def clear_caches(self):
        if self.datasite_owner_syncer is not None:
            self.datasite_owner_syncer.event_cache.clear_cache()
        if self.datasite_watcher_syncer is not None:
            self.datasite_watcher_syncer.datasite_watcher_cache.clear_cache()

    def delete_syftbox(self, verbose: bool = True):
        file_ids = self.connection_router.gather_all_file_and_folder_ids()
        start = time.time()
        self.connection_router.delete_multiple_files_by_ids(file_ids)
        end = time.time()
        if verbose:
            print(f"Deleted {len(file_ids)} files and folders in {end - start}s")
        self.connection_router.reset_caches()

    def _get_all_peer_platforms(self) -> List[BasePlatform]:
        all_platforms = set(
            [plat for p in self.version_manager.approved_peers for plat in p.platforms]
        )
        return list(all_platforms)

    def resolve_path(self, path: str | Path) -> Path:
        return resolve_path(path, syftbox_folder=self.syftbox_folder)

    def _resolve_dataset_owners_for_name(self, dataset_name: str) -> str | None:
        matches = []
        for dataset in self.dataset_manager.get_all():
            if dataset.name == dataset_name:
                matches.append(dataset.owner)
        return matches

    # def resolve_dataset_path(
    #     self, dataset_name: str, owner_email: str | None = None
    # ) -> Path:
    #     if owner_email is None:
    #         owner_emails = self._resolve_dataset_owners_for_name(dataset_name)
    #         if len(owner_emails) == 1:
    #             owner_email = owner_emails[0]
    #         else:
    #             raise ValueError(
    #                 f"Dataset {dataset_name} has 0 or multiple owners: {owner_emails}, please specify the owner_email"
    #             )

    #     return resolve_dataset_path(
    #         dataset_name, syftbox_folder=self.syftbox_folder, owner_email=owner_email
    #     )
