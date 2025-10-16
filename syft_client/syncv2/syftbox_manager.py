from pydantic import BaseModel, model_validator
from typing import List
from syft_client.syncv2.connections import ConnectionConfig
from syft_client.syncv2.syftbox_utils import random_email, random_base_path
from syft_client.syncv2.file_writer import FileWriter
from syft_client.syncv2.file_change_puller import ProposedFileChangePuller
from syft_client.syncv2.file_change_pusher import FileChangePusher
from syft_client.syncv2.file_change_handler import SyftboxFileChangeHandler
from syft_client.syncv2.connection_router import ConnectionRouter
from syft_client.syncv2.connections import (
    MemoryPlatformConnection,
    InMemoryPlatformConnectionConfig,
)
from syft_client.syncv2.proposed_filechange_handler import ProposedFileChangeHandler


class SyftboxManagerConfig(BaseModel):
    email: str
    base_path: str
    write_files: bool = True
    connection_configs: List[ConnectionConfig] = []

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


class SyftboxManager(BaseModel):
    file_writer: FileWriter
    base_path: str
    email: str
    dev_mode: bool = False
    file_change_puller: ProposedFileChangePuller
    file_change_pusher: FileChangePusher
    file_change_handler: SyftboxFileChangeHandler

    @classmethod
    def from_config(cls, config: SyftboxManagerConfig):
        manager_res = cls(
            base_path=config.base_path,
            email=config.email,
            connection_configs=config.connection_configs,
            write_files=config.write_files,
        )

        return manager_res

    @model_validator(mode="before")
    def pre_init(cls, data):
        write_files = data.get("write_files", True)

        data["file_writer"] = FileWriter(
            base_path=data["base_path"], write_files=write_files
        )
        data["handler"] = ProposedFileChangeHandler(write_files=write_files)
        data["file_change_puller"] = ProposedFileChangePuller(
            base_path=data["base_path"], handler=data["handler"]
        )
        data["file_change_handler"] = SyftboxFileChangeHandler()

        connections = [
            MemoryPlatformConnection.from_config(config)
            for config in data.get("connection_configs", [])
        ]
        data["file_change_pusher"] = FileChangePusher(
            base_path=data["base_path"],
            connection_router=ConnectionRouter(connections=connections),
        )
        return data

    @classmethod
    def pair_with_in_memory_connection(
        cls,
        email1: str | None = None,
        email2: str | None = None,
        base_path1: str | None = None,
        base_path2: str | None = None,
    ):
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
            sender_manager.file_change_pusher.on_file_change,
        )
        # this makes sure that a message travels from through our in memory platform from pusher to puller
        sender_manager.file_change_pusher.connection_router.connections.append(
            MemoryPlatformConnection.from_config(
                InMemoryPlatformConnectionConfig(
                    receiver_function=receiver_manager.file_change_puller.on_proposed_filechange_receive
                )
            )
        )
        # this make sure that when the receiver writes a file to disk, the file watcher picks it up
        receiver_manager.file_change_puller.handler.add_callback(
            "on_accept_file_change",
            receiver_manager.file_change_handler._handle_file_change,
        )

        return sender_manager, receiver_manager

    def send_file_change(self, path: str, content: str):
        self.file_writer.write_file(path, content)
