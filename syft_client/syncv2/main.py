from pathlib import Path
import random
from typing import Callable, ClassVar, Dict, List, Type
from pydantic import BaseModel, ConfigDict, model_validator


def random_email():
    return f"test{random.randint(1, 1000000)}@test.com"


def random_base_path():
    return f"/tmp/syftbox{random.randint(1, 1000000)}"


class FileWriter(BaseModel):
    base_path: str
    callbacks: Dict[str, List[Callable]]
    write_files: bool = True

    def add_callback(self, on: str, callback: Callable):
        if on not in self.callbacks:
            self.callbacks[on] = []
        self.callbacks[on].append(callback)

    def write_file(self, path: str, content: str):
        if self.write_files:
            with open(path, "w") as f:
                f.write(content)

        for callback in self.callbacks.get("write_file", []):
            callback(path, content)


class ProposedFileChangeEvent(BaseModel):
    path: str
    content: str


class SyftBoxProposedFileChangeHandler(BaseModel):
    """Responsible for downloading files and checking permissions"""

    model_config = ConfigDict(extra="allow")
    change_log: List = []
    _permission_cache: Dict = {}
    write_files: bool = True

    callbacks: Dict[str, List[Callable]] = {}

    def add_callback(self, on: str, callback: Callable):
        if on not in self.callbacks:
            self.callbacks[on] = []
        self.callbacks[on].append(callback)

    def check_permissions(self, path: str):
        pass

    def check_merge_conflicts(self, path: str):
        pass

    def write_file(self, path: str, content: str):
        pass

    def handle_proposed_filechange_event(self, event: ProposedFileChangeEvent):
        self.check_permissions(event.path)
        self.check_merge_conflicts(event.path)
        self.accept_file_change(event)

    def accept_file_change(self, event: ProposedFileChangeEvent):
        self.write_file(event.path, event.content)

        for callback in self.callbacks.get("on_accept_file_change", []):
            callback(event.path, event.content)


class SyftboxFileChangeHandler(BaseModel):
    """Responsible for writing files and checking permissions"""

    model_config = ConfigDict(extra="allow")

    def _handle_file_change(self, path: str, content: str):
        """we need this for monkey patching"""
        self.handle_file_change(path, content)

    def handle_file_change(self, path: str, content: str):
        print("handling file change")


class ProposedFileChangePuller(BaseModel):
    base_path: str
    handler: SyftBoxProposedFileChangeHandler

    def on_event_file_receive(self, path: str, content: str):
        self.handler.handle_proposed_filechange_event(
            ProposedFileChangeEvent(path=path, content=content)
        )


class ConnectionConfig(BaseModel):
    connection_type: ClassVar[Type["SyftboxPlatformConnection"]]


class SyftboxPlatformConnection(BaseModel):
    config: ConnectionConfig
    callbacks: Dict[str, List[Callable]] = {}

    def add_callback(self, on: str, callback: Callable):
        if on not in self.callbacks:
            self.callbacks[on] = []
        self.callbacks[on].append(callback)

    def propose_file_change(self, path: str, content: str):
        for callback in self.callbacks.get("on_propose_file_change", []):
            callback(path, content)

    @classmethod
    def from_config(cls, config: ConnectionConfig):
        return cls(config=config)


class SyftboxLocalFileMoverConnectionConfig(ConnectionConfig):
    destination_base_path: Path


class SyftboxLocalFileMoverConnection(SyftboxPlatformConnection):
    destination_base_path: Path | None = None
    callbacks: Dict[str, List[Callable]] = {}

    def add_callback(self, on: str, callback: Callable):
        if on not in self.callbacks:
            self.callbacks[on] = []
        self.callbacks[on].append(callback)

    @classmethod
    def from_config(cls, config: SyftboxLocalFileMoverConnectionConfig):
        return cls(config=config, destination_base_path=config.destination_base_path)

    def propose_file_change(self, path: str, content: str):
        destination_path = self.destination_base_path / path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.destination_base_path / path, "w") as f:
            f.write(content)
        for callback in self.callbacks.get("on_propose_file_change", []):
            callback(path, content)


class ConnectionRouter(BaseModel):
    connections: List[SyftboxPlatformConnection]

    def propose_file_change(self, path: str, content: str):
        # TODO: Implement connection routing logic
        self.connections[0].propose_file_change(path, content)


class FileChangePusher(BaseModel):
    base_path: str
    # callbacks: Dict[str, List[Callable]]
    connection_router: ConnectionRouter

    def on_file_change(self, path: str, content: str):
        self.connection_router.propose_file_change(path, content)

        # for callback in self.callbacks.get("on_file_change", []):
        #     callback(path, content)


class SyftboxManagerConfig(BaseModel):
    email: str
    base_path: str
    file_writer_callbacks: Dict[str, List[Callable]] = {}

    # this makes sure we call file handlers when a proposed file change is accepted
    add_proposed_file_change_handler_callbacks: bool = False
    add_sender_file_writer_callback: bool = False
    connection_configs: List[ConnectionConfig] = []
    write_files: bool = True

    @classmethod
    def for_local_file_move_connection(
        cls,
        email: str | None = None,
        base_path: str | None = None,
        file_writer_callback: Callable | None = None,
    ):
        base_path = base_path or random_base_path()
        email = email or random_email()
        connection_configs = [
            SyftboxLocalFileMoverConnectionConfig(
                destination_base_path=Path(base_path),
                connection_type=SyftboxLocalFileMoverConnection,
            )
        ]
        if file_writer_callback is None:
            file_writer_callbacks = {}
        else:
            file_writer_callbacks = {"write_file": [file_writer_callback]}
        return cls(
            email=email,
            base_path=base_path,
            connection_configs=connection_configs,
            add_proposed_file_change_handler_callbacks=True,
            add_sender_file_writer_callback=True,
            file_writer_callbacks=file_writer_callbacks,
        )

    @classmethod
    def for_in_memory_connection(
        cls,
        file_writer_callback: Callable | None = None,
        email: str | None = None,
        base_path: str | None = None,
    ):
        email = email or random_email()
        base_path = base_path or random_base_path()
        if file_writer_callback is None:
            file_writer_callbacks = {}
        else:
            file_writer_callbacks = {"write_file": [file_writer_callback]}
        return cls(
            write_files=False,
            add_proposed_file_change_handler_callbacks=True,
            file_writer_callbacks=file_writer_callbacks,
            email=email,
            base_path=base_path,
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
        )
        # this makes sure that when we write a file as sender, some callbacks may be triggered
        # such as receiving the file for the receiver or finding it for the local file watcher
        manager_res.file_writer.callbacks = config.file_writer_callbacks
        # manager_res.file_change_pusher.callbacks = config.file_change_pusher_callbacks

        if config.add_sender_file_writer_callback:
            manager_res.file_writer.add_callback(
                "write_file",
                manager_res.file_change_pusher.on_file_change,
            )

        if config.add_proposed_file_change_handler_callbacks:
            manager_res.file_change_puller.handler.add_callback(
                "on_accept_file_change",
                manager_res.file_change_handler._handle_file_change,
            )

        return manager_res

    @model_validator(mode="before")
    def pre_init(cls, data):
        write_files = data.get("write_files", True)

        data["file_writer"] = FileWriter(
            base_path=data["base_path"], write_files=write_files, callbacks={}
        )
        data["handler"] = SyftBoxProposedFileChangeHandler()
        data["file_change_puller"] = ProposedFileChangePuller(
            base_path=data["base_path"], handler=data["handler"]
        )
        data["file_change_handler"] = SyftboxFileChangeHandler()

        connections = [
            SyftboxLocalFileMoverConnection.from_config(config)
            for config in data.get("connection_configs", [])
        ]
        data["file_change_pusher"] = FileChangePusher(
            base_path=data["base_path"],
            callbacks={},
            connection_router=ConnectionRouter(connections=connections),
        )
        return data

    def _dev_add_file_writer_callback(self, callback: Callable):
        result_callbacks = self.file_writer.callbacks.get("write_file", [])
        result_callbacks.append(callback)
        self.file_writer.callbacks["write_file"] = result_callbacks

    @classmethod
    def pair_with_in_memory_connection(
        cls,
        email1: str | None = None,
        email2: str | None = None,
        base_path1: str | None = None,
        base_path2: str | None = None,
    ):
        # This is the callback stacktrace
        # FileWriter callback
        # manager.file_change_puller.on_event_file_receive for receiver
        # FileChangePuller callback
        # FileChangeHandler._handle_file_change

        # create first manager
        receiver_config = SyftboxManagerConfig.for_in_memory_connection(
            email=email1, base_path=base_path1
        )
        receiver_manager = cls.from_config(receiver_config)

        # create second manager
        sender_config = SyftboxManagerConfig.for_in_memory_connection(
            file_writer_callback=receiver_manager.file_change_puller.on_event_file_receive,
            email=email2,
            base_path=base_path2,
        )

        sender_manager = cls.from_config(sender_config)
        return sender_manager, receiver_manager

    @classmethod
    def pair_with_local_file_move_connection(
        cls,
        email1: str | None = None,
        email2: str | None = None,
        base_path1: str | None = None,
        base_path2: str | None = None,
    ):
        # This is the callback stacktrace
        # FileWriter callback
        # FileChangePusher.on_file_change
        # this eventually calls SyftboxLocalFileMoverConnection.propose_file_change
        # FileChangePuller.on_event_file_receive calls callback
        # FileChangeHandler._handle_file_change

        receiver_config = SyftboxManagerConfig.for_local_file_move_connection(
            email=email1,
            base_path=base_path1,
        )
        receiver_manager = cls.from_config(receiver_config)

        sender_config = SyftboxManagerConfig.for_local_file_move_connection(
            file_writer_callback=receiver_manager.file_change_puller.on_event_file_receive,
            email=email2,
            base_path=base_path2,
        )
        sender_manager = cls.from_config(sender_config)

        sender_manager.file_writer.add_callback(
            "write_file",
            sender_manager.file_change_pusher.on_file_change,
        )

        sender_manager.file_change_pusher.connection_router.connections[0].add_callback(
            "on_propose_filechange",
            receiver_manager.file_change_puller.on_event_file_receive,
        )

        return sender_manager, receiver_manager

    def write_file(self, path: str, content: str):
        self.file_writer.write_file(path, content)


class SyncManager(BaseModel):
    pass


def test_in_memory_connection():
    manager1, manager2 = SyftboxManager.pair_with_in_memory_connection()
    message_received = False

    def patch_file_receive(*args, **kwargs):
        nonlocal message_received
        message_received = True

    manager2.file_change_handler.handle_file_change = patch_file_receive
    manager1.write_file("test.txt", "Hello, world!")
    assert message_received


test_in_memory_connection()


def test_local_file_move_connection():
    manager1, manager2 = SyftboxManager.pair_with_local_file_move_connection()
    message_received = False

    def patch_file_receive(*args, **kwargs):
        nonlocal message_received
        message_received = True

    manager2.file_change_handler.handle_file_change = patch_file_receive

    manager1.write_file("test.txt", "Hello, world!")
    assert message_received


test_local_file_move_connection()
