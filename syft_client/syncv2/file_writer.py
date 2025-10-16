from pydantic import BaseModel
from typing import Dict, List, Callable


class FileWriter(BaseModel):
    base_path: str
    callbacks: Dict[str, List[Callable]] = {}
    write_files: bool = True

    def add_callback(self, on: str, callback: Callable):
        if on not in self.callbacks:
            self.callbacks[on] = []
        self.callbacks[on].append(callback)

    def write_file(self, path: str, content: str):
        if self.write_files:
            with open(path, "w") as f:
                f.write(content)

        for callback in self.callbacks.get("write_file", []):
            callback(path, content)
