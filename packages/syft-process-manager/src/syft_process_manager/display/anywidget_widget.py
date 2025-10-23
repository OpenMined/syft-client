"""Prototype anywidget implementation for ProcessHandle"""

import json
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import anywidget
import traitlets
from syft_process_manager.display.resources import load_resource
from syft_process_manager.runners import ProcessRunner, get_runner
from traitlets import observe

if TYPE_CHECKING:
    from syft_process_manager.handle import ProcessHandle


def detect_dark_mode() -> str:
    """Detect if Jupyter is in dark mode"""
    try:
        from jupyter_dark_detect import is_dark

        return "dark" if is_dark() else "light"
    except ImportError:
        return "light"


class ProcessWidget(anywidget.AnyWidget):
    """Widget for displaying process status with live updates"""

    _esm = load_resource("anywidget_render.js")
    _css = load_resource("anywidget_styles.css")

    config = traitlets.Dict(default_value={}).tag(sync=True)
    process_state = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    health = traitlets.Dict(allow_none=True, default_value=None).tag(sync=True)
    stdout_lines = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(
        sync=True
    )
    stderr_lines = traitlets.List(trait=traitlets.Unicode(), default_value=[]).tag(
        sync=True
    )
    theme = traitlets.Unicode("light").tag(sync=True)
    polling_active = traitlets.Bool(True).tag(sync=True)
    polling_interval = traitlets.Float(1.0).tag(sync=True)

    def __init__(self, process_handle: "ProcessHandle", **kwargs):
        # Extract only the paths we need to avoid holding a reference to mutable ProcessHandle
        super().__init__(**kwargs)

        self._process_state_path: Path = process_handle.config.process_state_path
        self._health_path: Path = process_handle.config.health_path
        self._stdout_path: Path = process_handle.config.stdout_path
        self._stderr_path: Path = process_handle.config.stderr_path
        self._runner: ProcessRunner = get_runner(process_handle.config.runner_type)
        self._polling_thread = None
        self._stop_polling = threading.Event()

        self.config = process_handle.config.model_dump(mode="json")

        self.theme = detect_dark_mode()
        self._start_polling()

    @observe("polling_active")
    def _on_polling_active_changed(self, change):
        """Restart polling thread when polling_active changes to True"""
        if change["new"] and not change["old"]:
            self._start_polling()

    def _start_polling(self):
        """Start background polling thread"""
        if self._polling_thread and self._polling_thread.is_alive():
            return

        self._stop_polling.clear()
        self._polling_thread = threading.Thread(
            target=self._poll_loop,
            daemon=True,
            name=f"ProcessWidget-{self.config.get('name', 'unknown')}",
        )
        self._polling_thread.start()

    def _stop_polling_thread(self):
        """Stop background polling thread"""
        if self._polling_thread and self._polling_thread.is_alive():
            self._stop_polling.set()
            self._polling_thread.join(timeout=2.0)

    def _poll_loop(self):
        """Background polling loop that updates widget state"""
        while not self._stop_polling.is_set() and self.polling_active:
            try:
                self._update_from_files()
            except Exception as e:
                print(f"Error polling process: {e}")

            self._stop_polling.wait(self.polling_interval)

    def _update_from_files(self):
        """Update widget state by reading from files directly"""
        state = self._read_process_state()
        if self.process_state != state:
            self.process_state = state

        health = self._read_json(self._health_path)
        if self.health != health:
            self.health = health

        stdout_lines = self._read_lines(self._stdout_path)
        if self.stdout_lines != stdout_lines:
            self.stdout_lines = stdout_lines

        stderr_lines = self._read_lines(self._stderr_path)
        if self.stderr_lines != stderr_lines:
            self.stderr_lines = stderr_lines

    def _read_process_state(self) -> dict | None:
        """Read process state file, return None if not running"""
        state = self._read_json(self._process_state_path)
        if state:
            if not self._runner.is_running_matching_create_time(
                state["pid"], state["process_create_time"]
            ):
                state = None
        return state

    def _read_json(self, path: Path) -> dict | None:
        """Read JSON file, return None if doesn't exist"""
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def _read_lines(self, path: Path) -> list[str]:
        """Read log lines, return last 20 lines"""
        if not path.exists():
            return []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines() if content else []
            return lines[-20:] if lines else []
        except Exception:
            return []

    def close(self):
        """Close the widget and stop polling thread"""
        self.polling_active = False
        self._stop_polling_thread()
        super().close()
