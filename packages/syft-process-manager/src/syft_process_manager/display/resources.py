import importlib.resources
from functools import lru_cache

ASSETS = "syft_process_manager.assets"


@lru_cache(maxsize=64)
def load_resource(fname: str, module: str = ASSETS) -> str:
    return importlib.resources.read_text(module, fname)
