from pydantic import BaseModel, ConfigDict


class SyftboxFileChangeHandler(BaseModel):
    """Responsible for writing files and checking permissions"""

    model_config = ConfigDict(extra="allow")

    def _handle_file_change(self, path: str, content: str):
        """we need this for monkey patching"""
        self.handle_file_change(path, content)

    def handle_file_change(self, path: str, content: str):
        print("handling file change")
