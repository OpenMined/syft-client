import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from syft_process_manager.constants import DEFAULT_PROCESS_MANAGER_DIR
from syft_process_manager.utils import find_free_port
from typing_extensions import Literal

ReadMode = Literal["head", "tail"]

_APP_THREAD = None
_SERVER_PORT = None

app = FastAPI(title="Syft Process Manager Widget Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development/notebook usage
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ReadLinesResponse(BaseModel):
    lines: list[str]
    total: int


@app.get("/read_lines", response_model=ReadLinesResponse)
def read_file_content(
    file_path: Path,
    mode: ReadMode = "tail",
    num_lines: int = 32,
) -> ReadLinesResponse:
    """Read content from a file, either head or tail."""
    if file_path.is_absolute():
        # Only allow files in the default process manager dir
        if not file_path.is_relative_to(DEFAULT_PROCESS_MANAGER_DIR):
            raise HTTPException(status_code=403, detail="Access Forbidden")
    else:  # relative path
        file_path = DEFAULT_PROCESS_MANAGER_DIR / file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        if mode == "head":
            selected_lines = lines[:num_lines]
        else:  # mode == "tail"
            selected_lines = lines[-num_lines:]
        return ReadLinesResponse(lines=selected_lines, total=len(lines))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


def _wait_for_startup(port: int, timeout: float = 5.0) -> None:
    """Wait for the FastAPI app to start up."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            import requests

            response = requests.get(f"http://localhost:{port}/health")
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError("FastAPI app failed to start within timeout")


def ensure_app_is_running() -> int:
    """Ensure the FastAPI app is running, return the port."""
    global _APP_THREAD, _SERVER_PORT
    if isinstance(_APP_THREAD, threading.Thread) and _APP_THREAD.is_alive():
        return _SERVER_PORT

    def run_app(port: int):
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
        )

    _SERVER_PORT = find_free_port()
    _APP_THREAD = threading.Thread(
        target=run_app,
        args=(_SERVER_PORT,),
        daemon=True,
    )
    _APP_THREAD.start()
    _wait_for_startup(_SERVER_PORT)
    return _SERVER_PORT
