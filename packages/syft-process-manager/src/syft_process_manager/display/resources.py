import importlib.resources
from functools import lru_cache
from pathlib import Path

ASSETS = "syft_process_manager.assets"
ASSETS_DIR = Path(__file__).parent.parent / "assets"


@lru_cache(maxsize=64)
def load_resource(fname: str, module: str = ASSETS) -> str:
    return importlib.resources.read_text(module, fname)
