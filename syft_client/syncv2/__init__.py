import random
from typing import Callable, List
from pydantic import BaseModel


def random_email():
    return f"test{random.randint(1, 1000000)}@test.com"


def random_base_path():
    return f"/tmp/syftbox{random.randint(1, 1000000)}"


class FileWriter(BaseModel):
    base_path: str

    def write_file(self, path: str, content: str):
        with open(path, "w") as f:
            f.write(content)


class DevFileWriter(FileWriter):
    callbacks: List[Callable]
    write_files: bool = False

    def write_file(self, path: str, content: str):
        if self.write_files:
            super().write_file(path, content)

        for callback in self.callbacks:
            callback(path, content)


class ProposedFileChangeEvent(BaseModel):
    path: str
    content: str


class SyftBoxFileChangeHandler:
    def handle_proposed_filechange_event(self, event: ProposedFileChangeEvent):
        pass


class Receiver(BaseModel):
    base_path: str
    handler: SyftBoxFileChangeHandler

    def on_event_file_receive(self, path: str):
        pass


class SyftboxManager(BaseModel):
    file_writer: FileWriter
    email: str

    def __init__(self, base_path: str, dev_mode: bool = False):
        self.file_writer = FileWriter(base_path)
        if dev_mode:
            self.receiver = Receiver(base_path=base_path, handler=self.handler)
            self.file_writer = DevFileWriter(
                base_path,
                callbacks=[],
                write_files=False,
            )

    def _dev_add_file_writer_callback(self, callback: Callable):
        self.file_writer.callbacks.append(callback)

    @classmethod
    def for_dev_pair(
        cls,
        email1: str | None = None,
        email2: str | None = None,
        base_path1: str | None = None,
        base_path2: str | None = None,
    ):
        email1 = email1 or random_email()
        email2 = email2 or random_email()
        base_path1 = base_path1 or random_base_path()
        base_path2 = base_path2 or random_base_path()
        manager1 = cls(email=email1, base_path=base_path1, dev_mode=True)
        manager2 = cls(email=email2, base_path=base_path2, dev_mode=True)
        manager1._dev_add_file_writer_callback(manager2.receiver.on_event_file_receive)
        return manager1, manager2

    def write_file(self, path: str, content: str):
        self.file_writer.write_file(path, content)


class SyncManager(BaseModel):
    pass


manager1, manager2 = SyftboxManager.for_dev_pair(
    email1="test1@test.com",
    email2="test2@test.com",
    base_path="/tmp/syftbox1",
    dev_mode=True,
)

manager1.write_file("test.txt", "Hello, world!")
manager2.write_file("test.txt", "Hello, world!")
