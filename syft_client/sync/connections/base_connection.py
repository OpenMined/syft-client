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

    def create_dataset_collection_folder(self, tag: str, owner_email: str) -> str:
        raise NotImplementedError()

    def share_dataset_collection(self, tag: str, users: list[str] | str) -> None:
        raise NotImplementedError()

    def upload_dataset_files(self, tag: str, files: dict[str, bytes]) -> None:
        raise NotImplementedError()

    def list_dataset_collections_as_do(self) -> list[str]:
        raise NotImplementedError()

    def list_dataset_collections_as_ds(self) -> list[str]:
        raise NotImplementedError()

    def download_dataset_collection(
        self, tag: str, owner_email: str
    ) -> dict[str, bytes]:
        raise NotImplementedError()
