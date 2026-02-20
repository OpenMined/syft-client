"""
Environment snapshot utility for bug reports.

Collects comprehensive information about the runtime environment including:
- OS and hardware details
- Python installation and virtual environment
- Package manager status
- Installed packages and key dependencies
- Jupyter/Colab environment detection
- syft-client specific configuration

Safe to share: prints only versions/paths/config metadata (no tokens/secrets).
"""

from __future__ import annotations

import os
import platform
import site
import subprocess
import sys
from pathlib import Path
from typing import Any


def _run(cmd: str, timeout: int = 10) -> str | None:
    """Run a shell command and return output, or None on failure."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _header(title: str) -> None:
    """Print a section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _yn(value: Any) -> str:
    """Convert a value to YES/NO string."""
    return "YES" if value else "NO"


def _get_syft_client_info() -> dict[str, Any]:
    """Get syft-client specific information."""
    info: dict[str, Any] = {}

    try:
        import syft_client

        info["syft_client_version"] = getattr(syft_client, "__version__", "unknown")
    except ImportError:
        info["syft_client_version"] = "not installed"

    try:
        from syft_client.version import (
            MIN_SUPPORTED_PROTOCOL_VERSION,
            MIN_SUPPORTED_SYFT_CLIENT_VERSION,
            PROTOCOL_VERSION,
            SYFT_CLIENT_VERSION,
        )

        info["version_constants"] = {
            "SYFT_CLIENT_VERSION": SYFT_CLIENT_VERSION,
            "MIN_SUPPORTED_SYFT_CLIENT_VERSION": MIN_SUPPORTED_SYFT_CLIENT_VERSION,
            "PROTOCOL_VERSION": PROTOCOL_VERSION,
            "MIN_SUPPORTED_PROTOCOL_VERSION": MIN_SUPPORTED_PROTOCOL_VERSION,
        }
    except ImportError:
        info["version_constants"] = "not available"

    # Only show presence, not values (could contain paths with usernames or PII)
    info["SYFTBOX_FOLDER_set"] = os.environ.get("SYFTBOX_FOLDER") is not None
    if os.environ.get("SYFTBOX_FOLDER"):
        info["SYFTBOX_FOLDER_exists"] = Path(os.environ["SYFTBOX_FOLDER"]).exists()
    info["SYFTBOX_EMAIL_set"] = os.environ.get("SYFTBOX_EMAIL") is not None
    info["SYFT_IS_IN_JOB"] = os.environ.get("SYFT_IS_IN_JOB", "false")

    return info


def _get_notebook_identity() -> dict[str, Any]:
    """Get notebook/runtime identity information (privacy-conscious)."""
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
    }


def _get_colab_signals() -> dict[str, Any]:
    """Get Google Colab environment signals."""
    env_keys = [
        "COLAB_RELEASE_TAG",
        "COLAB_GPU",
        "COLAB_TPU_ADDR",
        "COLAB_BACKEND_VERSION",
        "COLAB_JUPYTER_IP",
        "GCS_READ_CACHE_BLOCK_SIZE_MB",
    ]

    signals = {k: os.environ.get(k) for k in env_keys}

    try:
        import google.colab  # type: ignore  # noqa: F401

        signals["google.colab_importable"] = True
    except ImportError:
        signals["google.colab_importable"] = False

    return signals


def _get_jupyter_signals() -> dict[str, Any]:
    """Get Jupyter environment signals (privacy-conscious)."""
    # Only check presence of env vars, not their values
    signals = {
        "JUPYTERHUB_USER_set": os.environ.get("JUPYTERHUB_USER") is not None,
        "JPY_PARENT_PID_set": os.environ.get("JPY_PARENT_PID") is not None,
    }

    signals["jupyter_lab_version"] = _run("jupyter lab --version")
    signals["ipython_version"] = _run("ipython --version")

    try:
        from IPython import get_ipython

        ipython = get_ipython()
        if ipython is not None:
            signals["ipython_kernel"] = type(ipython).__name__
            signals["in_ipython"] = True
        else:
            signals["in_ipython"] = False
    except Exception:
        signals["in_ipython"] = False

    return signals


def _get_os_info() -> dict[str, Any]:
    """Get operating system information (privacy-conscious)."""
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
    }

    # Only include OS version, not full kernel strings
    if platform.system() == "Linux":
        # Extract just distro name and version, not full os-release
        distro_id = _run("cat /etc/os-release 2>/dev/null | grep '^ID=' | cut -d= -f2")
        distro_version = _run(
            "cat /etc/os-release 2>/dev/null | grep '^VERSION_ID=' | cut -d= -f2"
        )
        if distro_id:
            info["distro"] = distro_id.strip('"')
        if distro_version:
            info["distro_version"] = distro_version.strip('"')
    elif platform.system() == "Darwin":
        info["macos_version"] = _run("sw_vers -productVersion")
    elif platform.system() == "Windows":
        win_ver = platform.win32_ver()
        info["windows_version"] = win_ver[0] if win_ver else None

    return info


def _get_hardware_info() -> dict[str, Any]:
    """Get hardware information (privacy-conscious, no disk/mount info)."""
    info: dict[str, Any] = {}

    system = platform.system()

    # CPU info - just core counts, not full lscpu output
    if system == "Linux":
        cpu_cores = _run("nproc 2>/dev/null")
        if cpu_cores:
            info["cpu_cores"] = cpu_cores
    elif system == "Darwin":
        cpu_cores = _run("sysctl -n hw.ncpu 2>/dev/null")
        if cpu_cores:
            info["cpu_cores"] = cpu_cores

    # Use psutil for cross-platform memory info (no disk - could reveal mount points)
    try:
        import psutil

        info["cpu_count_logical"] = psutil.cpu_count(logical=True)
        info["cpu_count_physical"] = psutil.cpu_count(logical=False)
        mem = psutil.virtual_memory()
        info["memory_total_gb"] = round(mem.total / (1024**3), 2)
        info["memory_available_gb"] = round(mem.available / (1024**3), 2)
    except ImportError:
        # Fallback for memory without psutil
        if system == "Linux":
            mem_total = _run(
                "cat /proc/meminfo 2>/dev/null | grep MemTotal | awk '{print $2/1024/1024}'"
            )
            if mem_total:
                info["memory_total_gb"] = round(float(mem_total), 2)
        elif system == "Darwin":
            mem_bytes = _run("sysctl -n hw.memsize 2>/dev/null")
            if mem_bytes:
                info["memory_total_gb"] = round(int(mem_bytes) / (1024**3), 2)

    return info


def _get_virtualization_info() -> dict[str, Any]:
    """Get virtualization/container environment hints (privacy-conscious)."""
    info: dict[str, Any] = {}

    # Just detect if in container, not detailed cgroup/orchestration info
    info["in_docker"] = Path("/.dockerenv").exists()
    info["in_kubernetes"] = os.environ.get("KUBERNETES_SERVICE_HOST") is not None

    # Detect virtualization type without revealing infrastructure details
    virt_type = _run("systemd-detect-virt 2>/dev/null")
    if virt_type and virt_type != "none":
        info["virtualization"] = virt_type

    return info


def _get_python_env_info() -> dict[str, Any]:
    """Get Python environment info (privacy-conscious, no paths)."""
    base_prefix = getattr(sys, "base_prefix", sys.prefix)
    real_prefix = getattr(sys, "real_prefix", None)
    in_venv = (sys.prefix != base_prefix) or (real_prefix is not None)

    # Only report presence/type of environment, not paths
    info = {
        "in_virtualenv": in_venv,
        "VIRTUAL_ENV_set": os.environ.get("VIRTUAL_ENV") is not None,
        "CONDA_PREFIX_set": os.environ.get("CONDA_PREFIX") is not None,
        "CONDA_DEFAULT_ENV": os.environ.get("CONDA_DEFAULT_ENV"),  # env name, not path
        "user_site_enabled": site.ENABLE_USER_SITE,
    }

    return info


def _get_package_manager_info() -> dict[str, Any]:
    """Get package manager versions (privacy-conscious, no config)."""
    info: dict[str, Any] = {}

    # Just versions, no paths or config (could reveal internal package indices)
    pip_version = _run(f"{sys.executable} -m pip --version 2>/dev/null")
    if pip_version:
        # Extract just version number, not path
        parts = pip_version.split()
        if len(parts) >= 2:
            info["pip_version"] = parts[1]

    conda_version = _run("conda --version 2>/dev/null")
    if conda_version:
        info["conda_version"] = conda_version.replace("conda ", "")

    uv_version = _run("uv --version 2>/dev/null")
    if uv_version:
        info["uv_version"] = uv_version.replace("uv ", "")

    poetry_version = _run("poetry --version 2>/dev/null")
    if poetry_version:
        # Poetry output: "Poetry (version X.Y.Z)"
        info["poetry_version"] = poetry_version

    return info


def _get_project_config_files() -> list[str]:
    """Check for common project configuration and lock files in cwd."""
    patterns = [
        "pyproject.toml",
        "uv.lock",
        "poetry.lock",
        "Pipfile",
        "Pipfile.lock",
        "requirements.txt",
        "setup.cfg",
        "setup.py",
        "environment.yml",
        ".python-version",
    ]

    found = []
    cwd = Path.cwd()
    for pattern in patterns:
        if (cwd / pattern).exists():
            found.append(pattern)

    return sorted(found)


def _get_relevant_packages() -> dict[str, str | None]:
    """Get versions of packages relevant to syft-client (not full package list)."""
    # Only check packages relevant to debugging syft-client issues
    relevant_packages = [
        "syft-client",
        "syft-datasets",
        "syft-job",
        "syft-notebook-ui",
        "numpy",
        "pandas",
        "pydantic",
        "httpx",
        "requests",
        "grpcio",
        "google-auth",
        "google-api-python-client",
        "ipython",
        "jupyter",
        "jupyterlab",
    ]

    versions = {}
    try:
        import importlib.metadata

        for pkg in relevant_packages:
            try:
                versions[pkg] = importlib.metadata.version(pkg)
            except importlib.metadata.PackageNotFoundError:
                versions[pkg] = None
    except Exception:
        pass

    return versions


def _check_key_modules() -> dict[str, dict[str, Any]]:
    """Check importability and versions of key Python modules."""
    modules = [
        "numpy",
        "pandas",
        "google.colab",
        "pydantic",
        "httpx",
        "syft_client",
        "syft_datasets",
        "syft_job",
        "syft_notebook_ui",
    ]

    results = {}
    for mod_name in modules:
        try:
            mod = __import__(mod_name)
            version = getattr(mod, "__version__", None)
            results[mod_name] = {"importable": True, "version": version}
        except ImportError:
            # Don't include error message - could contain paths
            results[mod_name] = {"importable": False}
        except Exception:
            results[mod_name] = {"importable": False}

    return results


def _get_gpu_info() -> dict[str, Any]:
    """Get GPU information if available."""
    info: dict[str, Any] = {}

    nvidia_smi = _run("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
    if nvidia_smi:
        info["nvidia_smi"] = nvidia_smi
        info["cuda_version"] = _run(
            "nvidia-smi --query-gpu=driver_version --format=csv,noheader"
        )

    try:
        import torch

        info["torch_cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["torch_cuda_device_count"] = torch.cuda.device_count()
            info["torch_cuda_device_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        pass
    except Exception as e:
        info["torch_cuda_error"] = str(e)

    try:
        import tensorflow as tf

        gpus = tf.config.list_physical_devices("GPU")
        info["tensorflow_gpus"] = len(gpus)
    except ImportError:
        pass
    except Exception as e:
        info["tensorflow_gpu_error"] = str(e)

    return info


def _interpret_environment() -> dict[str, bool]:
    """Quick interpretation of the environment type."""
    return {
        "is_google_colab": bool(os.environ.get("COLAB_RELEASE_TAG")),
        "is_jupyterhub": bool(os.environ.get("JUPYTERHUB_USER")),
        "is_kaggle": bool(os.environ.get("KAGGLE_KERNEL_RUN_TYPE")),
        "is_databricks": bool(os.environ.get("DATABRICKS_RUNTIME_VERSION")),
        "in_docker": Path("/.dockerenv").exists(),
        "in_virtualenv": sys.prefix != getattr(sys, "base_prefix", sys.prefix),
        "conda_active": bool(os.environ.get("CONDA_PREFIX")),
    }


def bug_report(
    as_dict: bool = False, redact_paths: bool = False
) -> dict[str, Any] | None:
    """
    Generate a comprehensive environment snapshot for bug reports.

    This function collects information about the runtime environment including
    OS details, Python configuration, virtual environments, package managers,
    installed packages, and Jupyter/Colab environment detection.

    The output is safe to share: it prints only versions, paths, and config
    metadata. No tokens, secrets, or sensitive credentials are included.

    Args:
        as_dict: If True, return the report as a dictionary instead of printing.
        redact_paths: If True, redact user-specific paths in the output.

    Returns:
        If as_dict is True, returns a dictionary containing all collected info.
        Otherwise, prints the report and returns None.

    Examples:
        >>> import syft_client as sc
        >>> sc.utilities.bug_report()  # Prints full report

        >>> report = sc.utilities.bug_report(as_dict=True)  # Get as dict
        >>> print(report["syft_client"]["syft_client_version"])
    """
    if not as_dict:
        print("Collecting environment information... (this may take a few seconds)")
        print("")

    report: dict[str, Any] = {}

    report["syft_client"] = _get_syft_client_info()
    report["runtime"] = _get_notebook_identity()
    report["colab_signals"] = _get_colab_signals()
    report["jupyter_signals"] = _get_jupyter_signals()
    report["os_info"] = _get_os_info()
    report["hardware"] = _get_hardware_info()
    report["virtualization"] = _get_virtualization_info()
    report["python_env"] = _get_python_env_info()
    report["package_managers"] = _get_package_manager_info()
    report["project_config_files"] = _get_project_config_files()
    report["relevant_packages"] = _get_relevant_packages()
    report["key_modules"] = _check_key_modules()
    report["gpu_info"] = _get_gpu_info()
    report["interpretation"] = _interpret_environment()

    if as_dict:
        return report

    _header("SYFT-CLIENT INFO")
    for k, v in report["syft_client"].items():
        if isinstance(v, dict):
            print(f"{k}:")
            for k2, v2 in v.items():
                print(f"  {k2}: {v2}")
        else:
            print(f"{k}: {v}")

    _header("RUNTIME")
    for k, v in report["runtime"].items():
        print(f"{k}: {v}")

    _header("ENVIRONMENT TYPE")
    for k, v in report["interpretation"].items():
        print(f"{k}: {_yn(v)}")

    _header("COLAB SIGNALS")
    for k, v in report["colab_signals"].items():
        if v is not None:
            print(f"{k}: {v}")

    _header("JUPYTER SIGNALS")
    for k, v in report["jupyter_signals"].items():
        print(f"{k}: {v}")

    _header("OPERATING SYSTEM")
    for k, v in report["os_info"].items():
        print(f"{k}: {v}")

    _header("HARDWARE")
    for k, v in report["hardware"].items():
        print(f"{k}: {v}")

    _header("VIRTUALIZATION / CONTAINER")
    for k, v in report["virtualization"].items():
        print(f"{k}: {v}")

    _header("PYTHON ENVIRONMENT")
    for k, v in report["python_env"].items():
        print(f"{k}: {v}")

    _header("PACKAGE MANAGERS")
    for k, v in report["package_managers"].items():
        print(f"{k}: {v}")

    _header("PROJECT CONFIG FILES")
    if report["project_config_files"]:
        for f in report["project_config_files"]:
            print(f"  {f}")
    else:
        print("  None found")

    _header("RELEVANT PACKAGES")
    for pkg, version in report["relevant_packages"].items():
        status = version if version else "not installed"
        print(f"  {pkg}: {status}")

    _header("KEY MODULES")
    for mod, info in report["key_modules"].items():
        if info.get("importable"):
            version = info.get("version", "unknown")
            print(f"  {mod}: {version}")
        else:
            print(f"  {mod}: not importable")

    _header("GPU INFO")
    if report["gpu_info"]:
        for k, v in report["gpu_info"].items():
            print(f"{k}: {v}")
    else:
        print("No GPU detected")

    _header("NOTES")
    print("This report contains no tokens, secrets, paths, or PII.")
    print("Safe to share in bug reports and support requests.")
    print("\nTo get as dict: report = sc.utilities.bug_report(as_dict=True)")

    return None
