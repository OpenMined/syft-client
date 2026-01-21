from typing import List, Dict
from pydantic import Field
from syft_client.sync.events.file_change_event import FileChangeEventsMessage
from syft_client.sync.messages.proposed_filechange import ProposedFileChangesMessage
from uuid import uuid4
from pathlib import Path
from syft_client.sync.utils.syftbox_utils import create_event_timestamp
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
from pydantic import BaseModel, model_validator
from syft_client.sync.sync.caches.cache_file_writer_connection import FSFileConnection
from syft_client.sync.events.file_change_event import FileChangeEvent
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.sync.caches.cache_file_writer_connection import (
    CacheFileConnection,
    InMemoryCacheFileConnection,
)
from syft_client.sync.utils.syftbox_utils import get_event_hash_from_content


class ProposedEventFileOutdatedException(Exception):
    def __init__(self, file_path: str, hash_in_event: int, hash_on_disk: int):
        super().__init__(
            f"Proposed event for file {file_path} is outdated, hash in event: {hash_in_event}, hash on disk: {hash_on_disk}"
        )


class DataSiteOwnerEventCacheConfig(BaseModel):
    use_in_memory_cache: bool = True
    syftbox_folder: Path | None = None
    email: str | None = None
    events_base_path: Path | None = None

    @model_validator(mode="before")
    def pre_init(cls, data):
        if data.get("events_base_path") is None and data.get("base_path") is not None:
            base_path = data["base_path"]
            base_parent = base_path.parent
            data["events_base_path"] = base_parent / "events"
        return data


class DataSiteOwnerEventCache(BaseModelCallbackMixin):
    # we keep a list of heads, which are the latest events for each path

    events_messages_connection: CacheFileConnection = Field(
        default_factory=InMemoryCacheFileConnection
    )
    file_connection: CacheFileConnection = Field(
        default_factory=InMemoryCacheFileConnection
    )

    # file path to the hash of the filecontent
    file_hashes: Dict[str, int] = {}
    email: str

    @classmethod
    def from_config(cls, config: DataSiteOwnerEventCacheConfig):
        if config.use_in_memory_cache:
            return cls(
                events_connection=InMemoryCacheFileConnection[FileChangeEvent](),
                file_connection=InMemoryCacheFileConnection[str](),
                email=config.email,
            )
        else:
            if config.syftbox_folder is None:
                raise ValueError("base_path is required for non-in-memory cache")
            if config.email is None:
                raise ValueError("email is required for non-in-memory cache")
            syftbox_folder_name = Path(config.syftbox_folder).name
            my_datasite_folder = config.syftbox_folder / config.email
            syftbox_parent = Path(config.syftbox_folder).parent
            events_folder = syftbox_parent / f"{syftbox_folder_name}-events"
            cache = cls(
                events_messages_connection=FSFileConnection(
                    base_dir=events_folder, dtype=FileChangeEventsMessage
                ),
                file_connection=FSFileConnection(base_dir=my_datasite_folder),
                email=config.email,
            )
            cache._load_file_hashes_from_disk()
            return cache

    def _load_file_hashes_from_disk(self) -> float | None:
        """Load existing events from disk and populate file_hashes."""
        cached_messages = self.events_messages_connection.get_all()

        sorted_messages = sorted(cached_messages, key=lambda m: m.timestamp)

        for events_message in sorted_messages:
            for event in events_message.events:
                if event.is_deleted:
                    if event.path_in_datasite in self.file_hashes:
                        del self.file_hashes[event.path_in_datasite]
                else:
                    self.file_hashes[event.path_in_datasite] = event.new_hash

    @property
    def latest_cached_timestamp(self) -> float | None:
        cached_messages = self.events_messages_connection.get_all()
        if not cached_messages:
            return None
        return max(m.timestamp for m in cached_messages)

    def process_local_file_changes(self) -> FileChangeEventsMessage | None:
        new_events = []

        # Get current files on disk - normalize paths to Path objects
        current_files = {}
        for path, content in self.file_connection.get_items():
            path = Path(path)  # Normalize to Path
            if str(path).startswith("private"):
                continue
            if ".venv" in str(path):
                continue
            current_files[path] = content

        # Detect modifications and additions
        for path, content in current_files.items():
            current_hash = get_event_hash_from_content(content)
            if current_hash != self.file_hashes.get(path, None):
                timestamp = create_event_timestamp()
                event = FileChangeEvent(
                    id=uuid4(),
                    path_in_datasite=path,
                    content=content,
                    new_hash=current_hash,
                    old_hash=self.file_hashes.get(path),
                    submitted_timestamp=timestamp,
                    timestamp=timestamp,
                    datasite_email=self.email,
                    is_deleted=False,
                )
                new_events.append(event)

        # Detect deletions
        current_paths = set(current_files.keys())
        cached_paths = set(self.file_hashes.keys())
        deleted_paths = cached_paths - current_paths

        for deleted_path in deleted_paths:
            timestamp = create_event_timestamp()
            deletion_event = FileChangeEvent(
                id=uuid4(),
                path_in_datasite=deleted_path,
                content=None,
                old_hash=self.file_hashes[deleted_path],
                new_hash=None,
                submitted_timestamp=timestamp,
                timestamp=timestamp,
                datasite_email=self.email,
                is_deleted=True,
            )
            new_events.append(deletion_event)

        if new_events:
            events_message = FileChangeEventsMessage(events=new_events)
            # its already written so no need to write again
            self.add_events_message_to_local_cache(events_message, write_file=False)
            return events_message
        else:
            return None

    def clear_cache(self):
        self.events_messages_connection.clear_cache()
        self.file_connection.clear_cache()
        self.file_hashes = {}

    def has_conflict(self, proposed_event: ProposedFileChange) -> bool:
        if proposed_event.path_in_datasite not in self.file_hashes:
            if proposed_event.old_hash is None:
                return False
            else:
                raise ValueError(
                    f"File {proposed_event.path_in_datasite} is not in the cache but it does have an old hash"
                )
        return (
            self.file_hashes[proposed_event.path_in_datasite] != proposed_event.old_hash
        )

    def process_proposed_events_message(
        self, proposed_events_message: ProposedFileChangesMessage
    ) -> FileChangeEventsMessage | None:
        accepted_events_message = FileChangeEventsMessage(events=[])

        for proposed_filechange_event in proposed_events_message.proposed_file_changes:
            if self.has_conflict(proposed_filechange_event):
                hash_on_disk = self.file_hashes[
                    proposed_filechange_event.path_in_datasite
                ]
                raise ProposedEventFileOutdatedException(
                    proposed_filechange_event.path_in_datasite,
                    proposed_filechange_event.old_hash,
                    hash_on_disk,
                )
            else:
                accepted_event = FileChangeEvent.from_proposed_filechange(
                    proposed_filechange_event
                )
                accepted_events_message.events.append(accepted_event)
        if len(accepted_events_message.events) > 0:
            self.apply_accepted_events_message_to_cache(accepted_events_message)
            return accepted_events_message
        return None

    def apply_accepted_events_message_to_cache(
        self, accepted_events_message: FileChangeEventsMessage
    ):
        self.add_events_message_to_local_cache(accepted_events_message)

    def add_events_message_to_local_cache(
        self, accepted_events_message: FileChangeEventsMessage, write_file: bool = True
    ):
        self.events_messages_connection.write_file(
            path=accepted_events_message.message_filepath.as_string(),
            content=accepted_events_message,
        )

        for accepted_event in accepted_events_message.events:
            if accepted_event.is_deleted:
                # Handle deletion
                if accepted_event.path_in_datasite in self.file_hashes:
                    del self.file_hashes[accepted_event.path_in_datasite]

                if write_file:
                    self.file_connection.delete_file(accepted_event.path_in_datasite)

                for callback in self.callbacks.get("on_event_local_write", []):
                    callback(
                        accepted_event.path_in_datasite,
                        None,  # No content for deletions
                    )
            else:
                # Handle create/update
                self.file_hashes[accepted_event.path_in_datasite] = (
                    accepted_event.new_hash
                )

                if write_file:
                    self.file_connection.write_file(
                        accepted_event.path_in_datasite,
                        accepted_event.content,
                    )

                for callback in self.callbacks.get("on_event_local_write", []):
                    callback(
                        accepted_event.path_in_datasite,
                        accepted_event.content,
                    )

    def get_cached_events(self) -> List[FileChangeEvent]:
        events_messages = self.events_messages_connection.get_all()
        events = []
        for events_message in events_messages:
            events.extend(events_message.events)
        return events
