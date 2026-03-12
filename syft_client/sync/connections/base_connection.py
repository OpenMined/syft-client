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

    def watcher_send_proposed_file_changes_message(
        self, proposed_file_change_message: ProposedFileChangesMessage
    ):
        raise NotImplementedError()

    @classmethod
    def from_config(cls, config: ConnectionConfig):
        return config.connection_type.from_config(config)

    def owner_create_dataset_collection_folder(
        self, tag: str, content_hash: str, owner_email: str
    ) -> str:
        raise NotImplementedError()

    def owner_tag_dataset_collection_as_any(self, tag: str, content_hash: str) -> None:
        raise NotImplementedError()

    def owner_share_dataset_collection(
        self, tag: str, content_hash: str, users: list[str]
    ) -> None:
        raise NotImplementedError()

    def owner_upload_dataset_files(
        self, tag: str, content_hash: str, files: dict[str, bytes]
    ) -> None:
        raise NotImplementedError()

    def owner_list_dataset_collections(self) -> list[str]:
        raise NotImplementedError()

    def owner_list_all_dataset_collections_with_permissions(
        self,
    ) -> list[FileCollection]:
        """Returns list of FileCollection objects for DO's dataset collections."""
        raise NotImplementedError()

    def watcher_list_dataset_collections(self) -> list[dict]:
        """Returns list of dicts with keys: owner_email, tag, content_hash"""
        raise NotImplementedError()

    def watcher_download_dataset_collection(
        self, tag: str, content_hash: str, owner_email: str
    ) -> dict[str, bytes]:
        raise NotImplementedError()

    def owner_create_private_dataset_collection_folder(
        self, tag: str, content_hash: str, owner_email: str
    ) -> str:
        raise NotImplementedError()

    def owner_upload_private_dataset_files(
        self, tag: str, content_hash: str, files: dict[str, bytes]
    ) -> None:
        raise NotImplementedError()

    def owner_list_private_dataset_collections(self) -> list[FileCollection]:
        raise NotImplementedError()

    def owner_get_private_collection_file_metadatas(
        self, tag: str, content_hash: str, owner_email: str
    ) -> list[dict]:
        raise NotImplementedError()

    # =========================================================================
    # RAW BYTES TRANSPORT (used by ConnectionRouter for encryption)
    # =========================================================================

    def watcher_send_raw_bytes_to_inbox(
        self, recipient: str, filename: str, data: bytes
    ) -> None:
        raise NotImplementedError()

    def owner_download_next_raw_proposed_message_from_inbox(
        self, sender_email: str
    ) -> tuple[bytes, str] | None:
        """Download next message from inbox as raw bytes. Returns (data, file_id) or None."""
        raise NotImplementedError()

    def owner_write_raw_bytes_to_outbox(
        self, recipient: str, filename: str, data: bytes
    ) -> None:
        raise NotImplementedError()

    def watcher_download_raw_events_from_outbox(
        self, peer_email: str, since_timestamp: float | None
    ) -> list[bytes]:
        raise NotImplementedError()
