from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Callable


class ProposedFileChangeEvent(BaseModel):
    path: str
    content: str


class ProposedFileChangeHandler(BaseModel):
    """Responsible for downloading files and checking permissions"""

    model_config = ConfigDict(extra="allow")
    change_log: List = []
    _permission_cache: Dict = {}
    write_files: bool = True

    callbacks: Dict[str, List[Callable]] = {}

    def add_callback(self, on: str, callback: Callable):
        if on not in self.callbacks:
            self.callbacks[on] = []
        self.callbacks[on].append(callback)

    def check_permissions(self, path: str):
        pass

    def check_merge_conflicts(self, path: str):
        pass

    def write_file(self, path: str, content: str):
        pass

    def handle_proposed_filechange_event(self, event: ProposedFileChangeEvent):
        self.check_permissions(event.path)
        self.check_merge_conflicts(event.path)
        self.accept_file_change(event)

    def accept_file_change(self, event: ProposedFileChangeEvent):
        self.write_file(event.path, event.content)

        for callback in self.callbacks.get("on_accept_file_change", []):
            callback(event.path, event.content)
