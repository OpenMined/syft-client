from pydantic import BaseModel, Field
from pathlib import Path


class SyftBoxConfig(BaseModel):
    syftbox_folder: Path = Field(
        ..., description="Path to the SyftBox folder on the local filesystem."
    )
    email: str = Field(..., description="Email associated with the SyftBox.")

    @property
    def private_dir(self) -> Path:
        return self.syftbox_folder / "private"

    @property
    def public_dir(self) -> Path:
        return self.syftbox_folder / self.email / "public"
