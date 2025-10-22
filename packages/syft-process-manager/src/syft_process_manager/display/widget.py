"""Widget rendering for Jupyter notebooks"""

import uuid
from functools import lru_cache
from typing import Any

from jinja2 import Environment, PackageLoader
from syft_process_manager.display.resources import load_resource


@lru_cache(maxsize=1)
def get_jinja_env() -> Environment:
    """Get cached Jinja2 environment with template caching enabled"""
    return Environment(
        loader=PackageLoader("syft_process_manager", "assets"),
        autoescape=True,
    )


def detect_dark_mode() -> bool:
    """Detect if Jupyter is in dark mode"""
    try:
        from jupyter_dark_detect import is_dark

        return is_dark()
    except ImportError:
        return False


def get_theme_colors(is_dark_mode: bool) -> dict[str, str]:
    """Get theme-aware colors for the widget"""
    if is_dark_mode:
        # Dark mode colors
        return {
            "bg_color": "#1e1e1e",
            "border_color": "#3e3e3e",
            "text_color": "#e0e0e0",
            "label_color": "#a0a0a0",
            "code_bg": "#2d2d2d",
            "log_bg": "#1a1a1a",
            "error_bg": "#1a1a1a",
            "link_color": "#66b3ff",
            "log_text_color": "#9ca3af",
            "error_text_color": "#ff6b6b",
        }
    else:
        # Light mode colors
        return {
            "bg_color": "#ffffff",
            "border_color": "#ddd",
            "text_color": "#333",
            "label_color": "#666",
            "code_bg": "#f8f9fa",
            "log_bg": "#f8f9fa",
            "error_bg": "#fef2f2",
            "link_color": "#3498db",
            "log_text_color": "#374151",
            "error_text_color": "#d73a49",
        }


def render_process_widget(
    name: str,
    status: str,
    pid: int | None,
    uptime: str,
    backend_url: str,
    stdout_path: str,
    stderr_path: str,
) -> str:
    """Render process widget HTML for Jupyter notebook

    Args:
        name: Process name
        status: Process status (running/stopped/failed)
        pid: Process ID
        uptime: Human-readable uptime string
        backend_url: Base URL of the backend server for log polling
        stdout_path: Path to stdout log file
        stderr_path: Path to stderr log file

    Returns:
        HTML string for rendering in Jupyter
    """
    # Detect dark mode
    is_dark_mode = detect_dark_mode()

    # Get theme colors
    colors = get_theme_colors(is_dark_mode)

    # Status-specific colors and icons
    if status == "running":
        status_color = "#27ae60"
        status_icon = "✅"
    elif status == "unhealthy":
        status_color = "#f39c12"
        status_icon = "⚠️"
    else:  # stopped
        status_color = "#95a5a6"
        status_icon = "⭕"

    # Generate unique instance ID
    instance_id = str(uuid.uuid4())[:8]

    # Prepare context for template
    context: dict[str, Any] = {
        "name": name,
        "status": status.title(),
        "status_color": status_color,
        "status_icon": status_icon,
        "uptime": uptime,
        "pid": pid,
        "instance_id": instance_id,
        **colors,
    }

    # Add log polling script
    log_script = load_resource("log_polling.js")
    # Replace placeholders
    log_script = (
        log_script.replace("BACKEND_URL_PLACEHOLDER", backend_url)
        .replace("STDOUT_PATH_PLACEHOLDER", stdout_path)
        .replace("STDERR_PATH_PLACEHOLDER", stderr_path)
        .replace("INSTANCE_ID_PLACEHOLDER", instance_id)
        .replace("LOG_TEXT_COLOR_PLACEHOLDER", colors["log_text_color"])
        .replace("ERROR_TEXT_COLOR_PLACEHOLDER", colors["error_text_color"])
    )
    context["log_polling_script"] = log_script

    # Load and render template using cached environment
    env = get_jinja_env()
    template = env.get_template("process_widget.html")

    return template.render(**context)
