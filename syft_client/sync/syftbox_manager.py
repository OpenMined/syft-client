from pathlib import Path
from pydantic import ConfigDict
from syft_client.sync.utils.print_utils import print_peer_added
from syft_client.sync.platforms.base_platform import BasePlatform
from pydantic import BaseModel, model_validator, Field
from typing import List
from syft_client.sync.peers.peer_list import PeerList
from syft_client.sync.sync.datasite_outbox_puller import DatasiteOutboxPuller
from syft_client.sync.sync.caches.datasite_watcher_cache import DataSiteWatcherCache
from syft_client.sync.connections.base_connection import (
    ConnectionConfig,
    SyftboxPlatformConnection,
)
from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.utils.syftbox_utils import random_email, random_base_path
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


class SyftboxManagerConfig(BaseModel):
    email: str
    base_path: str
    write_files: bool = True
    only_ds: bool = False
    only_datasite_owner: bool = False
    connection_configs: List[ConnectionConfig] = []

    @classmethod
    def for_colab(
        cls, email: str, only_ds: bool = False, only_datasite_owner: bool = False
    ):
        if not only_ds and not only_datasite_owner:
            raise ValueError(
                "At least one of only_ds or only_datasite_owner must be True"
            )

        connection_configs = [GdriveConnectionConfig(email=email, token_path=None)]
        return cls(
            email=email,
            base_path="/",
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            connection_configs=connection_configs,
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

        connection_configs = [
            GdriveConnectionConfig(email=email, token_path=token_path)
        ]
        return cls(
            email=email,
            base_path="/tmp/syftbox",
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
            connection_configs=connection_configs,
        )

    @classmethod
    def base_config_for_in_memory_connection(
        cls,
        email: str | None = None,
        base_path: str | None = None,
        write_files: bool = False,
        only_ds: bool = False,
        only_datasite_owner: bool = False,
    ):
        base_path = base_path or random_base_path()
        email = email or random_email()
        return cls(
            email=email,
            base_path=base_path,
            write_files=write_files,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
        )

    @classmethod
    def for_google_drive_testing_connection(
        cls,
        email: str,
        token_path: Path,
        base_path: str | None = None,
        write_files: bool = False,
        only_ds: bool = False,
        only_datasite_owner: bool = False,
    ):
        base_path = base_path or random_base_path()
        email = email or random_email()
        connection_configs = [
            GdriveConnectionConfig(email=email, token_path=token_path)
        ]
        return cls(
            email=email,
            base_path=base_path,
            write_files=write_files,
            connection_configs=connection_configs,
            only_ds=only_ds,
            only_datasite_owner=only_datasite_owner,
        )


class SyftboxManager(BaseModel):
    # needed for peers
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_writer: FileWriter
    base_path: str
    email: str
    dev_mode: bool = False
    proposed_file_change_pusher: ProposedFileChangePusher | None = None
    datasite_outbox_puller: DatasiteOutboxPuller | None = None

    proposed_file_change_handler: ProposedFileChangeHandler | None = None
    job_file_change_handler: JobFileChangeHandler | None = None

    peers: PeerList = Field(default_factory=PeerList)

    @classmethod
    def from_config(cls, config: SyftboxManagerConfig):
        manager_res = cls(
            base_path=config.base_path,
            email=config.email,
            connection_configs=config.connection_configs,
            write_files=config.write_files,
            only_ds=config.only_ds,
            only_datasite_owner=config.only_datasite_owner,
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
        return cls.from_config(
            SyftboxManagerConfig.for_jupyter(
                email=email,
                only_ds=only_ds,
                only_datasite_owner=only_datasite_owner,
                token_path=token_path,
            )
        )

    @model_validator(mode="before")
    def pre_init(cls, data):
        write_files = data.get("write_files", True)

        # for in memory configs we set those later
        connections = [
            SyftboxPlatformConnection.from_config(config)
            for config in data.get("connection_configs", [])
        ]

        connection_router = ConnectionRouter(connections=connections)

        data["file_writer"] = FileWriter(
            base_path=data["base_path"], write_files=write_files
        )

        # if we also have an owner
        init_handlers = not data.get("only_ds", False)
        if init_handlers:
            data["proposed_file_change_handler"] = ProposedFileChangeHandler(
                write_files=write_files, connection_router=connection_router
            )

            data["job_file_change_handler"] = JobFileChangeHandler()

        init_pullers_pushers = not data.get("only_datasite_owner", False)
        if init_pullers_pushers:
            datasite_watcher_cache = DataSiteWatcherCache(
                connection_router=connection_router,
            )
            data["proposed_file_change_pusher"] = ProposedFileChangePusher(
                base_path=data["base_path"],
                email=data["email"],
                connection_router=connection_router,
                datasite_watcher_cache=datasite_watcher_cache,
            )

            data["datasite_outbox_puller"] = DatasiteOutboxPuller(
                connection_router=connection_router,
                datasite_watcher_cache=datasite_watcher_cache,
            )

        return data

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
    ):
        receiver_config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=do_email,
            base_path=base_path1,
            token_path=do_token_path,
            only_ds=False,
            only_datasite_owner=True,
        )

        receiver_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=ds_email,
            base_path=base_path2,
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
            sender_manager.add_peer(receiver_manager.email)
            receiver_manager.add_peer(sender_manager.email)
        if load_peers:
            receiver_manager.load_peers()
            sender_manager.load_peers()

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
    ):
        # this doesnt contain the connections, as we need to set them after creation
        receiver_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email1,
            base_path=base_path1,
            only_ds=False,
            only_datasite_owner=True,
        )

        do_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email2,
            base_path=base_path2,
            only_ds=True,
            only_datasite_owner=False,
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
            ds_manager.add_peer(do_manager.email)
            do_manager.add_peer(ds_manager.email)

        return ds_manager, do_manager

    def add_peer(self, peer_email: str):
        existing_emails = [p.email for p in self.peers]
        if peer_email in existing_emails:
            print(f"Peer {peer_email} already exists, skipping")

        if self.is_do:
            peer = self.connection_router.add_peer_as_do(peer_email=peer_email)
        else:
            peer = self.connection_router.add_peer_as_ds(peer_email=peer_email)
        self.peers.append(peer)
        print_peer_added(peer)

    @property
    def is_do(self) -> bool:
        return self.proposed_file_change_handler is not None

    def sync(self):
        peer_emails = [peer.email for peer in self.peers]
        if self.is_do:
            self.proposed_file_change_handler.sync(peer_emails)
        else:
            # ds
            self.datasite_outbox_puller.sync_down(peer_emails)

    def load_peers(self):
        if self.is_do:
            peers = self.connection_router.get_peers_as_do()
        else:
            peers = self.connection_router.get_peers_as_ds()

        self.peers = PeerList(peers)

    def add_connection(self, connection: SyftboxPlatformConnection):
        # all connection routers are pointers to the same object for in memory setup
        if not isinstance(connection, InMemoryPlatformConnection):
            raise ValueError(
                "Only InMemoryPlatformConnections can be added to the manager"
            )
        if self.proposed_file_change_handler is not None:
            connection_router = self.proposed_file_change_handler.connection_router
        elif self.proposed_file_change_pusher is not None:
            connection_router = self.proposed_file_change_pusher.connection_router
        elif self.datasite_outbox_puller is not None:
            connection_router = self.datasite_outbox_puller.connection_router
        elif self.job_file_change_handler is not None:
            connection_router = self.job_file_change_handler.connection_router
        else:
            raise ValueError("No connection router found")

        connection_router.connections.append(connection)

    def send_file_change(self, path: str, content: str):
        self.file_writer.write_file(path, content)

    def get_all_accepted_events_do(self) -> List[FileChangeEvent]:
        return self.proposed_file_change_handler.connection_router.get_all_accepted_events_do()

    @property
    def connection_router(self) -> ConnectionRouter:
        # for DOs we have a handler, for DSs we have a pusher
        if self.proposed_file_change_handler is not None:
            return self.proposed_file_change_handler.connection_router
        else:
            return self.proposed_file_change_pusher.connection_router

    def delete_syftbox(self):
        self.connection_router.delete_syftbox()

    def _get_all_peer_platforms(self) -> List[BasePlatform]:
        all_platforms = set([plat for p in self.peers for plat in p.platforms])
        return list(all_platforms)
