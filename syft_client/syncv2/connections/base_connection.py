from typing import ClassVar, Type
from pydantic import BaseModel
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChangesMessage


class ConnectionConfig(BaseModel):
    connection_type: ClassVar[Type["SyftboxPlatformConnection"]]


class SyftboxPlatformConnection(BaseModel):
    config: ConnectionConfig | None = None

    def send_propose_file_change_message(
        self, proposed_file_change_message: ProposedFileChangesMessage
    ):
        raise NotImplementedError()

    @classmethod
    def from_config(cls, config: ConnectionConfig):
        return cls(config=config)
