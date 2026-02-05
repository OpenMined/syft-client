"""Systemd user service installer for syft-bg."""

import subprocess
import sys
from pathlib import Path

SERVICE_NAME = "syft-bg"
SERVICE_FILE = f"{SERVICE_NAME}.service"

SERVICE_TEMPLATE = """\
[Unit]
Description=SyftBox Background Services
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
ExecStart={python} -m syft_bg start
ExecStop={python} -m syft_bg stop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
"""


def get_systemd_user_dir() -> Path:
    """Get the systemd user service directory."""
    return Path.home() / ".config" / "systemd" / "user"


def get_service_path() -> Path:
    """Get the full path to the service file."""
    return get_systemd_user_dir() / SERVICE_FILE


def install_service() -> tuple[bool, str]:
    """Install syft-bg as a systemd user service.

    Returns:
        (success, message) tuple
    """
    service_dir = get_systemd_user_dir()
    service_path = get_service_path()

    try:
        # Create directory if needed
        service_dir.mkdir(parents=True, exist_ok=True)

        # Generate service file with current Python interpreter
        python_path = sys.executable
        service_content = SERVICE_TEMPLATE.format(python=python_path)

        # Write service file
        service_path.write_text(service_content)

        # Reload systemd daemon
        result = subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return (False, f"Failed to reload systemd: {result.stderr}")

        # Enable service (start on boot)
        result = subprocess.run(
            ["systemctl", "--user", "enable", SERVICE_NAME],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return (False, f"Failed to enable service: {result.stderr}")

        return (True, f"Service installed: {service_path}")

    except PermissionError:
        return (False, f"Permission denied writing to {service_path}")
    except FileNotFoundError:
        return (False, "systemctl not found - systemd may not be available")
    except Exception as e:
        return (False, str(e))


def uninstall_service() -> tuple[bool, str]:
    """Uninstall syft-bg systemd user service.

    Returns:
        (success, message) tuple
    """
    service_path = get_service_path()

    try:
        # Stop service if running
        subprocess.run(
            ["systemctl", "--user", "stop", SERVICE_NAME],
            capture_output=True,
            text=True,
        )

        # Disable service
        subprocess.run(
            ["systemctl", "--user", "disable", SERVICE_NAME],
            capture_output=True,
            text=True,
        )

        # Remove service file
        if service_path.exists():
            service_path.unlink()

        # Reload systemd daemon
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            capture_output=True,
            text=True,
        )

        return (True, f"Service uninstalled: {service_path}")

    except FileNotFoundError:
        return (False, "systemctl not found - systemd may not be available")
    except Exception as e:
        return (False, str(e))


def get_service_status() -> tuple[bool, str]:
    """Get the status of the syft-bg systemd service.

    Returns:
        (is_active, status_text) tuple
    """
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", SERVICE_NAME],
            capture_output=True,
            text=True,
        )
        is_active = result.returncode == 0
        status = result.stdout.strip()
        return (is_active, status)
    except FileNotFoundError:
        return (False, "systemd not available")
    except Exception as e:
        return (False, str(e))
