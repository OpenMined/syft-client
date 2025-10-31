from pydantic import BaseModel
from typing import List, Dict, Tuple
from syft_client.sync.messages.proposed_filechange import ProposedFileChange
from syft_client.sync.events.file_change_event import FileChangeEvent
from pydantic import Field
from syft_client.sync.callback_mixin import BaseModelCallbackMixin
from syft_client.sync.sync.caches.cache_file_writer_connection import (
    CacheFileConnection,
    InMemoryCacheFileConnection,
)

"""
There are reasons why we want to support merges right now
Even though we have a single merger, we have multiple writers
If these writers are making writes that are not conflicting, we should support them
"""


class ProposedEventFileOutdatedException(Exception):
    def __init__(self, file_path: str, hash_in_event: int, hash_on_disk: int):
        super().__init__(
            f"Proposed event for file {file_path} is outdated, hash in event: {hash_in_event}, hash on disk: {hash_on_disk}"
        )


class DataSiteOwnerEventCache(BaseModelCallbackMixin):
    # we keep a list of heads, which are the latest events for each path

    events_connection: CacheFileConnection[FileChangeEvent] = Field(
        default_factory=lambda: InMemoryCacheFileConnection[FileChangeEvent]()
    )
    file_connection: CacheFileConnection[str] = Field(
        default_factory=lambda: InMemoryCacheFileConnection[str]()
    )

    # file path to the hash of the filecontent
    file_hashes: Dict[str, int] = {}

    def has_conflict(self, proposed_event: ProposedFileChange) -> bool:
        if proposed_event.path not in self.file_hashes:
            if proposed_event.old_hash is None:
                return False
            else:
                raise ValueError(
                    f"File {proposed_event.path} is not in the cache but it does have an old hash"
                )
        return self.file_hashes[proposed_event.path] != proposed_event.old_hash

    def process_proposed_event(self, proposed_event: ProposedFileChange):
        if self.has_conflict(proposed_event):
            hash_on_disk = self.file_hashes[proposed_event.path]
            raise ProposedEventFileOutdatedException(
                proposed_event.path, proposed_event.old_hash, hash_on_disk
            )
        else:
            result_event = self.apply_propposed_event_to_cache(proposed_event)
            return result_event

    def apply_propposed_event_to_cache(self, proposed_event: ProposedFileChange):
        event: FileChangeEvent = FileChangeEvent.from_proposed_filechange(
            proposed_event
        )
        self.add_event_to_local_cache(event)
        return event

    def add_event_to_local_cache(self, event: FileChangeEvent):
        self.file_hashes[event.path] = event.new_hash
        self.file_connection.write_file(event.path, event.content)
        self.events_connection.write_file(event.eventfile_filepath(), event)

        for callback in self.callbacks.get("on_event_local_write", []):
            callback(event.path, event.content)

    def get_cached_events(self) -> List[FileChangeEvent]:
        return self.events_connection.get_all()
