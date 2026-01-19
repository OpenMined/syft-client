from typing import ClassVar, Type
from pydantic import BaseModel
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage


class FileCollection(BaseModel):
    """A collection of files that can be shared and synced."""

    folder_id: str
    tag: str
    content_hash: str
    has_any_permission: bool = False


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

    def create_dataset_collection_folder(
        self, tag: str, content_hash: str, owner_email: str
    ) -> str:
        raise NotImplementedError()

    def share_dataset_collection(
        self, tag: str, content_hash: str, users: list[str] | str
    ) -> None:
        raise NotImplementedError()

    def upload_dataset_files(
        self, tag: str, content_hash: str, files: dict[str, bytes]
    ) -> None:
        raise NotImplementedError()

    def list_dataset_collections_as_do(self) -> list[str]:
        raise NotImplementedError()

    def list_all_dataset_collections_as_do_with_permissions(
        self,
    ) -> list[FileCollection]:
        """Returns list of FileCollection objects for DO's dataset collections."""
        raise NotImplementedError()

    def list_dataset_collections_as_ds(self) -> list[dict]:
        """Returns list of dicts with keys: owner_email, tag, content_hash"""
        raise NotImplementedError()

    def download_dataset_collection(
        self, tag: str, content_hash: str, owner_email: str
    ) -> dict[str, bytes]:
        raise NotImplementedError()
