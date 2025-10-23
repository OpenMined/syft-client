from pydantic import ConfigDict, Field
from typing import List, Dict, Callable
from syft_client.syncv2.events.file_change_event import FileChangeEvent
from syft_client.syncv2.connections.connection_router import ConnectionRouter
from syft_client.syncv2.messages.proposed_filechange import ProposedFileChange
from syft_client.syncv2.sync.caches.datasite_owner_cache import DataSiteOwnerEventCache
from syft_client.syncv2.callback_mixin import BaseModelCallbackMixin


class ProposedFileChangeHandler(BaseModelCallbackMixin):
    """Responsible for downloading files and checking permissions"""

    model_config = ConfigDict(extra="allow")
    event_cache: DataSiteOwnerEventCache = Field(
        default_factory=lambda: DataSiteOwnerEventCache(is_new_cache=True)
    )
    write_files: bool = True
    connection_router: ConnectionRouter

    def init_new_store(self):
        assert len(self.event_cache.id2node) == 1
        event = next(iter(self.event_cache.heads)).event
        self.write_event_to_backing_platform(event)
        print("EVENTS IN INIT_NEW_STORE", self.connection_router.get_all_events())

    def check_permissions(self, path: str):
        pass

    def handle_proposed_filechange_event(self, event: ProposedFileChange):
        self.check_permissions(event.path)

        # we may also get merge events
        event, merge_events = self.event_cache.process_proposed_event(event)
        all_resulting_events = [event] + merge_events
        for event in all_resulting_events:
            self.write_event_local(event)

        for event in all_resulting_events:
            self.write_event_to_backing_platform(event)

    def write_event_to_backing_platform(self, event: FileChangeEvent):
        self.connection_router.write_event_to_backing_platform(event)

    def write_file_filesystem(self, path: str, content: str):
        if self.write_files:
            raise NotImplementedError("Writing files to filesystem is not implemented")

    def write_event_local(self, event: ProposedFileChange):
        self.write_file_filesystem(event.path, event.content)

        for callback in self.callbacks.get("on_event_local_write", []):
            callback(event.path, event.content)
