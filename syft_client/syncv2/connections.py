from typing import ClassVar, Type, Callable
from pydantic import BaseModel


class ConnectionConfig(BaseModel):
    connection_type: ClassVar[Type["SyftboxPlatformConnection"]]


class SyftboxPlatformConnection(BaseModel):
    config: ConnectionConfig

    def propose_file_change(self, path: str, content: str):
        raise NotImplementedError()

    @classmethod
    def from_config(cls, config: ConnectionConfig):
        return cls(config=config)


class InMemoryPlatformConnectionConfig(ConnectionConfig):
    receiver_function: Callable | None = None


class MemoryPlatformConnection(SyftboxPlatformConnection):
    receiver_function: Callable | None = None

    @classmethod
    def from_config(cls, config: InMemoryPlatformConnectionConfig):
        return cls(config=config, receiver_function=config.receiver_function)

    def propose_file_change(self, path: str, content: str):
        self.receiver_function(path, content)
