import base64
from pydantic import BaseModel
from typing import Dict, List, Callable
from pathlib import Path


class FileWriter(BaseModel):
    base_path: Path
    callbacks: Dict[str, List[Callable]] = {}
    write_files: bool = True

    def add_callback(self, on: str, callback: Callable):
        if on not in self.callbacks:
            self.callbacks[on] = []
        self.callbacks[on].append(callback)

    def write_file(self, path: str, content: str):
        if self.write_files:
            if content.startswith("base64:"):
                # Binary content: decode base64 and write as bytes
                binary_data = base64.b64decode(content[7:])
                with open(path, "wb") as f:
                    f.write(binary_data)
            else:
                # Text content: write as-is
                with open(path, "w") as f:
                    f.write(content)

        for callback in self.callbacks.get("write_file", []):
            callback(path, content)
