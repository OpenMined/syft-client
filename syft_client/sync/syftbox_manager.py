from pathlib import Path
import copy
from concurrent.futures import ThreadPoolExecutor
import time
from pydantic import ConfigDict
from syft_job.client import JobClient, JobsList
from syft_job.job_runner import SyftJobRunner
from syft_job import SyftJobConfig
from syft_datasets.config import SyftBoxConfig
from syft_datasets.dataset_manager import SyftDatasetManager
from syft_client.sync.platforms.gdrive_files_platform import GdriveFilesPlatform
from syft_client.sync.utils.print_utils import (
    print_peer_added,
    print_peer_added_to_platform,
    print_peer_adding_to_platform,
)
from syft_client.sync.platforms.base_platform import BasePlatform
from pydantic import BaseModel, PrivateAttr
from typing import List
from syft_client.sync.sync.caches.datasite_watcher_cache import (
    DataSiteWatcherCacheConfig,
)
from syft_client.sync.sync.caches.datasite_owner_cache import (
    DataSiteOwnerEventCacheConfig,
)
from syft_client.sync.peers.peer_list import PeerList
from syft_client.sync.peers.peer import Peer, PeerState
from syft_client.sync.sync.datasite_outbox_puller import DatasiteOutboxPuller
from syft_client.sync.connections.base_connection import (
    SyftboxPlatformConnection,
)
from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.utils.syftbox_utils import (
    random_email,
    random_syftbox_folder_for_testing,
)
from syft_client.sync.file_writer import FileWriter

from syft_client.sync.sync.proposed_file_change_pusher import ProposedFileChangePusher
from syft_client.sync.job_file_change_handler import JobFileChangeHandler
from syft_client.sync.connections.connection_router import ConnectionRouter

from syft_client.sync.connections.drive.grdrive_config import GdriveConnectionConfig
from syft_client.sync.connections.inmemory_connection import (
    InMemoryPlatformConnection,
)
from syft_client.sync.sync.proposed_filechange_handler import (
    ProposedFileChangeHandler,
)
from syft_client.sync.sync.proposed_filechange_handler import (
    ProposedFileChangeHandlerConfig,
)
from syft_client.sync.sync.proposed_file_change_pusher import (
    ProposedFileChangePusherConfig,
)
from syft_client.sync.sync.datasite_outbox_puller import DatasiteOutboxPullerConfig
import os

COLAB_DEFAULT_SYFTBOX_FOLDER = Path("/")
JUPYTER_DEFAULT_SYFTBOX_FOLDER = Path.home() / "SyftBox"


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

    proposed_file_change_handler_config: ProposedFileChangeHandlerConfig

    proposed_file_change_pusher_config: ProposedFileChangePusherConfig
    datasite_outbox_puller_config: DatasiteOutboxPullerConfig
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
        connection_configs = [GdriveConnectionConfig(email=email, token_path=None)]
        proposed_file_change_handler_config = ProposedFileChangeHandlerConfig(
            email=email,
            connection_configs=connection_configs,
            cache_config=DataSiteOwnerEventCacheConfig(
                email=email,
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
            ),
        )
        proposed_file_change_pusher_config = ProposedFileChangePusherConfig(
            syftbox_folder=syftbox_folder,
            email=email,
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache, syftbox_folder=syftbox_folder
            ),
        )
        datasite_outbox_puller_config = DatasiteOutboxPullerConfig(
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
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
        return cls(
            email=email,
            syftbox_folder=syftbox_folder,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            connection_configs=connection_configs,
            use_in_memory_cache=False,
            proposed_file_change_handler_config=proposed_file_change_handler_config,
            proposed_file_change_pusher_config=proposed_file_change_pusher_config,
            datasite_outbox_puller_config=datasite_outbox_puller_config,
            dataset_manager_config=dataset_manager_config,
            job_client_config=job_client_config,
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

        connection_configs = [
            GdriveConnectionConfig(email=email, token_path=token_path)
        ]
        proposed_file_change_handler_config = ProposedFileChangeHandlerConfig(
            email=email,
            connection_configs=connection_configs,
            cache_config=DataSiteOwnerEventCacheConfig(
                email=email,
                use_in_memory_cache=False,
                syftbox_folder=syftbox_folder,
                connection_configs=connection_configs,
            ),
        )
        proposed_file_change_pusher_config = ProposedFileChangePusherConfig(
            syftbox_folder=syftbox_folder,
            email=email,
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=False,
                syftbox_folder=syftbox_folder,
                connection_configs=connection_configs,
            ),
        )
        datasite_outbox_puller_config = DatasiteOutboxPullerConfig(
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=False,
                syftbox_folder=syftbox_folder,
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
        return cls(
            email=email,
            syftbox_folder=syftbox_folder,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            use_in_memory_cache=False,
            proposed_file_change_handler_config=proposed_file_change_handler_config,
            proposed_file_change_pusher_config=proposed_file_change_pusher_config,
            datasite_outbox_puller_config=datasite_outbox_puller_config,
            dataset_manager_config=dataset_manager_config,
            job_client_config=job_client_config,
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
    ):
        syftbox_folder = syftbox_folder or random_syftbox_folder_for_testing()
        email = email or random_email()

        proposed_file_change_handler_config = ProposedFileChangeHandlerConfig(
            email=email,
            write_files=write_files,
            cache_config=DataSiteOwnerEventCacheConfig(
                email=email,
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
            ),
        )
        proposed_file_change_pusher_config = ProposedFileChangePusherConfig(
            email=email,
            syftbox_folder=syftbox_folder,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache, syftbox_folder=syftbox_folder
            ),
        )
        datasite_outbox_puller_config = DatasiteOutboxPullerConfig(
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache, syftbox_folder=syftbox_folder
            ),
            connection_configs=[],
        )

        dataset_manager_config = SyftBoxConfig(
            syftbox_folder=syftbox_folder,
            email=email,
        )
        job_client_config = SyftJobConfig(
            syftbox_folder=Path(syftbox_folder),
            email=email,
        )

        return cls(
            email=email,
            syftbox_folder=syftbox_folder,
            write_files=write_files,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            use_in_memory_cache=use_in_memory_cache,
            proposed_file_change_handler_config=proposed_file_change_handler_config,
            proposed_file_change_pusher_config=proposed_file_change_pusher_config,
            datasite_outbox_puller_config=datasite_outbox_puller_config,
            dataset_manager_config=dataset_manager_config,
            job_client_config=job_client_config,
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
    ):
        syftbox_folder = syftbox_folder or random_syftbox_folder_for_testing()
        email = email or random_email()
        connection_configs = [
            GdriveConnectionConfig(email=email, token_path=token_path)
        ]
        proposed_file_change_handler_config = ProposedFileChangeHandlerConfig(
            email=email,
            connection_configs=connection_configs,
            cache_config=DataSiteOwnerEventCacheConfig(
                email=email,
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
            ),
        )
        proposed_file_change_pusher_config = ProposedFileChangePusherConfig(
            syftbox_folder=syftbox_folder,
            email=email,
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
                connection_configs=connection_configs,
            ),
        )
        datasite_outbox_puller_config = DatasiteOutboxPullerConfig(
            connection_configs=connection_configs,
            datasite_watcher_cache_config=DataSiteWatcherCacheConfig(
                use_in_memory_cache=use_in_memory_cache,
                syftbox_folder=syftbox_folder,
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
        return cls(
            email=email,
            syftbox_folder=syftbox_folder,
            write_files=write_files,
            proposed_file_change_handler_config=proposed_file_change_handler_config,
            proposed_file_change_pusher_config=proposed_file_change_pusher_config,
            datasite_outbox_puller_config=datasite_outbox_puller_config,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            use_in_memory_cache=False,
            dataset_manager_config=dataset_manager_config,
            job_client_config=job_client_config,
        )


class SyftboxManager(BaseModel):
    # needed for peers
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_writer: FileWriter
    syftbox_folder: Path
    email: str
    dev_mode: bool = False
    proposed_file_change_pusher: ProposedFileChangePusher | None = None
    datasite_outbox_puller: DatasiteOutboxPuller | None = None

    proposed_file_change_handler: ProposedFileChangeHandler | None = None
    job_file_change_handler: JobFileChangeHandler | None = None
    dataset_manager: SyftDatasetManager | None = None
    job_client: JobClient | None = None
    job_runner: SyftJobRunner | None = None

    _approved_peers: List[Peer] = PrivateAttr(default_factory=list)
    _peer_requests: List[Peer] = PrivateAttr(default_factory=list)
    _outstanding_peer_requests: List[Peer] = PrivateAttr(default_factory=list)

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
            combined = PeerList(self._approved_peers + self._peer_requests)
        else:
            peers = copy.deepcopy(self._outstanding_peer_requests)
            for peer in peers:
                peer.state = PeerState.ACCEPTED
            combined = PeerList(peers)

        return combined

    @classmethod
    def from_config(cls, config: SyftboxManagerConfig):
        file_writer = FileWriter(
            base_path=config.syftbox_folder, write_files=config.write_files
        )

        proposed_file_change_handler = None
        job_file_change_handler = None
        proposed_file_change_pusher = None
        datasite_outbox_puller = None
        job_runner = None

        dataset_manager = SyftDatasetManager.from_config(config.dataset_manager_config)
        job_client = JobClient.from_config(config.job_client_config)

        if config.only_datasite_owner:
            proposed_file_change_handler = ProposedFileChangeHandler.from_config(
                config.proposed_file_change_handler_config
            )

            job_file_change_handler = JobFileChangeHandler()
            job_runner = SyftJobRunner.from_config(config.job_client_config)

        if not config.only_datasite_owner:
            proposed_file_change_pusher = ProposedFileChangePusher.from_config(
                config.proposed_file_change_pusher_config
            )
            datasite_outbox_puller = DatasiteOutboxPuller.from_config(
                config.datasite_outbox_puller_config
            )

        manager_res = cls(
            syftbox_folder=config.syftbox_folder,
            email=config.email,
            file_writer=file_writer,
            proposed_file_change_handler=proposed_file_change_handler,
            job_file_change_handler=job_file_change_handler,
            proposed_file_change_pusher=proposed_file_change_pusher,
            datasite_outbox_puller=datasite_outbox_puller,
            dataset_manager=dataset_manager,
            job_client=job_client,
            job_runner=job_runner,
        )

        return manager_res

    @classmethod
    def for_colab(
        cls, email: str, only_ds: bool = False, only_datasite_owner: bool = False
    ):
        return cls.from_config(
            SyftboxManagerConfig.for_colab(
                email=email,
                only_ds=only_ds,
                only_datasite_owner=only_datasite_owner,
            )
        )

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
        return cls.from_config(
            SyftboxManagerConfig.for_jupyter(
                email=email,
                only_ds=only_ds,
                only_datasite_owner=only_datasite_owner,
                token_path=token_path,
            )
        )

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
    ):
        receiver_config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=do_email,
            syftbox_folder=base_path1,
            use_in_memory_cache=use_in_memory_cache,
            token_path=do_token_path,
            only_ds=False,
            only_datasite_owner=True,
        )

        receiver_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=ds_email,
            syftbox_folder=base_path2,
            use_in_memory_cache=use_in_memory_cache,
            token_path=ds_token_path,
            only_ds=True,
            only_datasite_owner=False,
        )
        sender_manager = cls.from_config(sender_config)

        # this makes sure that when we write a file as sender, the inactive file watcher picks it up
        sender_manager.file_writer.add_callback(
            "write_file",
            sender_manager.proposed_file_change_pusher.on_file_change,
        )

        # this makes sure that when we receive a message, the handler is called
        # receiver_manager.proposed_file_change_puller.add_callback(
        #     "on_proposed_filechange_receive",
        #     receiver_manager.proposed_file_change_handler.handle_proposed_filechange_event,
        # )
        # this make sure that when the receiver writes a file to disk,
        # the file watcher picks it up
        # we use the underscored method to allow for monkey patching
        receiver_manager.proposed_file_change_handler.event_cache.add_callback(
            "on_event_local_write",
            receiver_manager.job_file_change_handler._handle_file_change,
        )

        if add_peers:
            # DS creates peer request
            sender_manager.add_peer(receiver_manager.email)
            # DO approves the peer request automatically (for backward compatibility)
            receiver_manager.load_peers()
            receiver_manager.approve_peer_request(sender_manager.email)
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
    ):
        # this doesnt contain the connections, as we need to set them after creation
        receiver_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email1,
            syftbox_folder=base_path1,
            only_ds=False,
            only_datasite_owner=True,
            use_in_memory_cache=use_in_memory_cache,
        )

        do_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email2,
            syftbox_folder=base_path2,
            only_ds=True,
            only_datasite_owner=False,
            use_in_memory_cache=use_in_memory_cache,
        )
        ds_manager = cls.from_config(sender_config)

        # this makes sure that when we write a file as sender, the inactive file watcher picks it up
        ds_manager.file_writer.add_callback(
            "write_file",
            ds_manager.proposed_file_change_pusher.on_file_change,
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

        sender_backing_store = ds_manager.proposed_file_change_pusher.connection_router.connection_for_eventlog().backing_store
        receiver_connection = InMemoryPlatformConnection(
            receiver_function=sender_receiver_function,
            backing_store=sender_backing_store,
            owner_email=do_manager.email,
        )
        do_manager.add_connection(receiver_connection)

        # this make sure that when the receiver writes a file to disk,
        # the file watcher picks it up
        # we use the underscored method to allow for monkey patching
        do_manager.proposed_file_change_handler.event_cache.add_callback(
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

    def add_peer(self, peer_email: str, force: bool = False, verbose: bool = True):
        existing_emails = [p.email for p in self._approved_peers]
        if peer_email in existing_emails and not force:
            print(f"Peer {peer_email} already exists, skipping")
        else:
            if self.is_do:
                # this is a no-op for DOs
                platform = GdriveFilesPlatform()
                if verbose:
                    print_peer_adding_to_platform(peer_email, platform.module_path)
                    print_peer_added_to_platform(peer_email, platform.module_path)
                peer = Peer(email=peer_email, platforms=[platform])
                self.approve_peer_request(peer_email, verbose=False)
            else:
                peer = self.connection_router.add_peer_as_ds(peer_email=peer_email)
                # we only do this for DSes
                self._outstanding_peer_requests.append(peer)
                print_peer_added(peer)

    def submit_bash_job(self, *args, sync=True, **kwargs):
        job_dir = self.job_client.submit_bash_job(*args, **kwargs)
        self.push_job_files(job_dir)

    def submit_python_job(self, *args, sync=True, **kwargs):
        job_dir = self.job_client.submit_python_job(*args, **kwargs)
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

            self.proposed_file_change_pusher.on_file_change(
                relative_file_path, process_now=last_file
            )

    @property
    def is_do(self) -> bool:
        return self.proposed_file_change_handler is not None

    def sync(self):
        self.load_peers()
        if self.is_do:
            peer_emails = [peer.email for peer in self._approved_peers]
            self.proposed_file_change_handler.sync(peer_emails)
        else:
            # ds
            peer_emails = [peer.email for peer in self._outstanding_peer_requests]
            self.datasite_outbox_puller.sync_down(peer_emails)

    def load_peers(self):
        if self.is_do:
            approved = self.connection_router.get_approved_peers_as_do()
            requests = self.connection_router.get_peer_requests_as_do()
            outstanding = []
        else:
            # DS sees all peers as approved (no request concept for DS)
            approved = []
            requests = []
            outstanding = self.connection_router.get_peers_as_ds()

        self._approved_peers = approved
        self._peer_requests = requests
        self._outstanding_peer_requests = outstanding

    def check_peer_request_exists(self, email: str) -> bool:
        return any(p.email == email for p in self._peer_requests)

    def approve_peer_request(
        self,
        email_or_peer: str | Peer,
        verbose: bool = True,
        peer_must_exist: bool = True,
    ):
        """
        Approve a pending peer request. DO only.

        Args:
            email_or_peer: Email string or Peer object to approve
        """
        if not self.is_do:
            raise ValueError("Only Data Owners can approve peer requests")

        email = email_or_peer if isinstance(email_or_peer, str) else email_or_peer.email

        # Find peer in requests
        peer_request_exists = any(p.email == email for p in self._peer_requests)
        if peer_must_exist and not peer_request_exists:
            raise ValueError(
                f"Peer {email} not found in pending requests."
                f"Use client.peers to see current requests."
            )

        # Update state in GDrive
        self.connection_router.update_peer_state(email, PeerState.ACCEPTED.value)

        # Move from requests to approved
        self._peer_requests = [p for p in self._peer_requests if p.email != email]

        # TODO, once we have more platforms, we need to check for which platform
        accepted_peer = Peer(
            email=email, platforms=[GdriveFilesPlatform()], state=PeerState.ACCEPTED
        )
        self._approved_peers.append(accepted_peer)

        if verbose:
            print(f"✓ Approved peer request from {email}")

    def reject_peer_request(self, email_or_peer: str | Peer):
        """
        Reject a pending peer request. DO only.

        Args:
            email_or_peer: Email string or Peer object to reject
        """
        if not self.is_do:
            raise ValueError("Only Data Owners can reject peer requests")

        email = email_or_peer if isinstance(email_or_peer, str) else email_or_peer.email

        # Find peer in requests
        peer = None
        for p in self._peer_requests:
            if p.email == email:
                peer = p
                break

        if peer is None:
            raise ValueError(
                f"Peer {email} not found in pending requests. "
                f"Use client.peers to see current requests."
            )

        # Update state in GDrive
        self.connection_router.update_peer_state(email, PeerState.REJECTED.value)

        # Remove from requests (don't add to approved)
        self._peer_requests = [p for p in self._peer_requests if p.email != email]

        print(f"✗ Rejected peer request from {email}")

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

    def process_approved_jobs(self, stream_output: bool = True) -> None:
        """
        Process approved jobs. Automatically calls sync() after processing

        Args:
            stream_output: If True (default), stream output in real-time.
                        If False, capture output at end.

        PRE_SYNC defaults to "true", so auto-sync is enabled by default.
        To disable auto-sync, set: PRE_SYNC=false
        """
        self.job_runner.process_approved_jobs(stream_output=stream_output)
        if os.environ.get("PRE_SYNC", "true").lower() == "true":
            self.sync()

    def add_connection(self, connection: SyftboxPlatformConnection):
        # all connection routers are pointers to the same object for in memory setup
        if not isinstance(connection, InMemoryPlatformConnection):
            raise ValueError(
                "Only InMemoryPlatformConnections can be added to the manager"
            )
        if self.proposed_file_change_handler is not None:
            self.proposed_file_change_handler.connection_router.add_connection(
                connection
            )
        if self.proposed_file_change_pusher is not None:
            self.proposed_file_change_pusher.connection_router.add_connection(
                connection
            )
            self.proposed_file_change_pusher.datasite_watcher_cache.connection_router.add_connection(
                connection
            )
        if self.datasite_outbox_puller is not None:
            self.datasite_outbox_puller.datasite_watcher_cache.connection_router.add_connection(
                connection
            )
            self.datasite_outbox_puller.connection_router.add_connection(connection)

    def send_file_change(self, path: str | Path, content: str):
        self.file_writer.write_file(path, content)

    def get_all_accepted_events_do(self) -> List[FileChangeEvent]:
        return self.proposed_file_change_handler.connection_router.get_all_accepted_events_messages_do()

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
        collection_tag = dataset.name

        # Create collection folder
        self.connection_router.create_dataset_collection_folder(
            tag=collection_tag, owner_email=self.email
        )

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

        # Upload files
        self.connection_router.upload_dataset_files(collection_tag, files)

        # Share with users
        self.connection_router.share_dataset_collection(collection_tag, users)

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
        if self.dataset_manager is None:
            raise ValueError("Dataset manager is not set")

        if not self.is_do:
            raise ValueError("Only dataset owners can share datasets")

        # Verify dataset exists
        dataset = self.dataset_manager.get(name=tag, datasite=self.email)
        if dataset is None:
            raise ValueError(f"Dataset {tag} not found")

        # Share collection
        self.connection_router.share_dataset_collection(tag, users)

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
        # for DOs we have a handler, for DSs we have a pusher
        if self.proposed_file_change_handler is not None:
            return self.proposed_file_change_handler.connection_router
        else:
            return self.proposed_file_change_pusher.connection_router

    def clear_caches(self):
        if self.proposed_file_change_handler is not None:
            self.proposed_file_change_handler.event_cache.clear_cache()
        if self.datasite_outbox_puller is not None:
            self.datasite_outbox_puller.datasite_watcher_cache.clear_cache()

        if self.proposed_file_change_pusher is not None:
            self.proposed_file_change_pusher.datasite_watcher_cache.clear_cache()

    def delete_syftbox(self, verbose: bool = True):
        file_ids = self.connection_router.gather_all_file_and_folder_ids()
        start = time.time()
        self.connection_router.delete_multiple_files_by_ids(file_ids)
        end = time.time()
        if verbose:
            print(f"Deleted {len(file_ids)} files and folders in {end - start}s")
        self.connection_router.reset_caches()

    def _get_all_peer_platforms(self) -> List[BasePlatform]:
        all_platforms = set([plat for p in self._peers for plat in p.platforms])
        return list(all_platforms)
