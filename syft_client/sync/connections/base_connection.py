from typing import ClassVar, Type
from pydantic import BaseModel
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage


class ConnectionConfig(BaseModel):
    connection_type: ClassVar[Type["SyftboxPlatformConnection"]]


class SyftboxPlatformConnection(BaseModel):
    config: ConnectionConfig | None = None

    def send_proposed_file_changes_message(
        self, proposed_file_change_message: ProposedFileChangesMessage
    ):
        raise NotImplementedError()

    @classmethod
    def from_config(cls, config: ConnectionConfig):
        return config.connection_type.from_config(config)
