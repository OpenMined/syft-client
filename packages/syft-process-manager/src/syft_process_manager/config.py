from pathlib import Path

import pydantic_settings


class ProcessManagerConfig(pydantic_settings.BaseSettings):
    base_dir: Path = Path.home() / ".syft_process_manager"
