import time
from typing import List

from pydantic import BaseModel, model_validator

from syft_client.syncv2.connections.base_connection import (
    ConnectionConfig,
    SyftboxPlatformConnection,
)
from syft_client.syncv2.connections.connection_router import ConnectionRouter
from syft_client.syncv2.connections.gdrive_transport_v2 import GDriveFilesTransport
from syft_client.syncv2.connections.inmemory_connection import (
    InMemoryPlatformConnection,
)
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.file_writer import FileWriter
from syft_client.syncv2.job_file_change_handler import JobFileChangeHandler
from syft_client.syncv2.syftbox_utils import random_base_path, random_email
from syft_client.syncv2.sync.caches.datasite_watcher_cache import DataSiteWatcherCache
from syft_client.syncv2.sync.datasite_outbox_puller import DatasiteOutboxPuller
from syft_client.syncv2.sync.proposed_file_change_pusher import ProposedFileChangePusher
from syft_client.syncv2.sync.proposed_filechange_handler import (
    ProposedFileChangeHandler,
)


class SyftboxManagerConfig(BaseModel):
    email: str
    base_path: str
    write_files: bool = True
    connection_configs: List[ConnectionConfig] = []
    dev_mode: bool = False

    @classmethod
    def base_config_for_in_memory_connection(
        cls,
        email: str | None = None,
        base_path: str | None = None,
        write_files: bool = False,
    ):
        base_path = base_path or random_base_path()
        email = email or random_email()
        return cls(
            email=email,
            base_path=base_path,
            write_files=write_files,
        )

    @classmethod
    def for_google_drive_testing_connection(
        cls,
        email: str,
        base_path: str | None = None,
        write_files: bool = False,
    ):
        base_path = base_path or random_base_path()
        email = email or random_email()
        connection_configs = [ConnectionConfig(connection_type=GDriveFilesTransport)]
        return cls(
            email=email,
            base_path=base_path,
            write_files=write_files,
            connection_configs=connection_configs,
        )


class SyftboxManager(BaseModel):
    file_writer: FileWriter
    base_path: str
    email: str
    dev_mode: bool = False
    proposed_file_change_pusher: ProposedFileChangePusher
    proposed_file_change_handler: ProposedFileChangeHandler
    datasite_outbox_puller: DatasiteOutboxPuller

    job_file_change_handler: JobFileChangeHandler

    @classmethod
    def from_config(cls, config: SyftboxManagerConfig):
        manager_res = cls(
            base_path=config.base_path,
            email=config.email,
            connection_configs=config.connection_configs,
            write_files=config.write_files,
            dev_mode=config.dev_mode,
        )

        return manager_res

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

        # todo: is this used?
        data["proposed_file_change_handler"] = ProposedFileChangeHandler(
            write_files=write_files, connection_router=connection_router
        )

        data["proposed_file_change_pusher"] = ProposedFileChangePusher(
            base_path=data["base_path"],
            connection_router=connection_router,
        )

        datasite_watcher_cache = DataSiteWatcherCache(
            connection_router=connection_router,
        )

        data["datasite_outbox_puller"] = DatasiteOutboxPuller(
            connection_router=connection_router,
            datasite_watcher_cache=datasite_watcher_cache,
        )

        data["job_file_change_handler"] = JobFileChangeHandler()
        return data

    @classmethod
    def pair_with_google_drive_testing_connection(
        cls,
        email1: str,
        email2: str,
        base_path1: str | None = None,
        base_path2: str | None = None,
    ):
        receiver_config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=email1,
            base_path=base_path1,
        )

        receiver_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.for_google_drive_testing_connection(
            email=email2,
            base_path=base_path2,
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
        return sender_manager, receiver_manager

    def init_dataowner_store(self):
        self.proposed_file_change_handler.init_new_store()

    @classmethod
    def pair_with_in_memory_connection(
        cls,
        email1: str | None = None,
        email2: str | None = None,
        base_path1: str | None = None,
        base_path2: str | None = None,
    ):
        # this doesnt contain the connections, as we need to set them after creation
        receiver_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email1,
            base_path=base_path1,
        )

        receiver_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.base_config_for_in_memory_connection(
            email=email2,
            base_path=base_path2,
        )
        sender_manager = cls.from_config(sender_config)

        # this makes sure that when we write a file as sender, the inactive file watcher picks it up
        sender_manager.file_writer.add_callback(
            "write_file",
            sender_manager.proposed_file_change_pusher.on_file_change,
        )
        # this makes sure that a message travels from through our in memory platform from pusher to puller
        receiver_receive_function = receiver_manager.proposed_file_change_handler.pull_and_process_next_proposed_filechange
        sender_in_memory_connection = InMemoryPlatformConnection(
            receiver_function=receiver_receive_function
        )
        sender_manager.add_connection(sender_in_memory_connection)

        # this make sure we can do communication the other way, it also makes sure we have a fake backing store for the receiver
        # so we can store events in memory
        # we also make sure we write to the same backing store so we get consistent state
        # sender_receiver_function = (
        #     sender_manager.proposed_file_change_handler.on_proposed_filechange_receive
        # )
        def sender_receiver_function(*args, **kwargs):
            pass

        sender_backing_store = sender_manager.proposed_file_change_pusher.connection_router.connection_for_eventlog().backing_store
        receiver_connection = InMemoryPlatformConnection(
            receiver_function=sender_receiver_function,
            backing_store=sender_backing_store,
        )
        receiver_manager.add_connection(receiver_connection)

        # this make sure that when the receiver writes a file to disk,
        # the file watcher picks it up
        # we use the underscored method to allow for monkey patching
        receiver_manager.proposed_file_change_handler.event_cache.add_callback(
            "on_event_local_write",
            receiver_manager.job_file_change_handler._handle_file_change,
        )

        # init receiver store so we have a head
        receiver_manager.init_dataowner_store()

        return sender_manager, receiver_manager

    def add_connection(self, connection: SyftboxPlatformConnection):
        self.proposed_file_change_handler.connection_router.connections.append(
            connection
        )
        # this should be the same for the puller and pusher, as they use refernces to the same router
        # self.proposed_file_change_puller.connection_router.connections.append(connection)
        # self.proposed_file_change_pusher.connection_router.connections.append(connection)

    def send_file_change(self, path: str, content: str):
        self.file_writer.write_file(path, content)

    def get_all_events(self) -> List[FileChangeEvent]:
        return self.proposed_file_change_handler.connection_router.get_all_events()

    def run_forever(self):
        print("SyftboxManager started")
        while True:
            time.sleep(2)
            print("SyftboxManager running...")
