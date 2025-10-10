"""Environment detection and configuration module"""

from enum import Enum
from typing import Optional


class Environment(Enum):
    """Supported Python environments"""

    COLAB = "colab"
    JUPYTER = "jupyter"
    REPL = "repl"
    # Future environments can be added here
    # VSCODE = "vscode"
    # PYCHARM = "pycharm"
    # DATABRICKS = "databricks"


class EnvironmentDetector:
    """Detects and manages Python environment information"""

    @staticmethod
    def detect() -> Environment:
        """
        Detect which Python environment we're running in

        Returns:
            Environment enum value
        """
        # Check for Google Colab first (most specific)
        try:
            import google.colab

            return Environment.COLAB
        except ImportError:
            pass
        except (
            AttributeError
        ):  # sometimes we're seeing an error in "import google.colab" when called from background
            return Environment.COLAB

        # Check for Jupyter/IPython with multiple indicators
        try:
            # Method 1: Check for IPython
            get_ipython = __builtins__.get("get_ipython", None)
            if get_ipython is not None:
                # Method 2: Check IPKernelApp in config (classic Jupyter)
                if "IPKernelApp" in get_ipython().config:
                    return Environment.JUPYTER

                # Method 3: Check for ZMQInteractiveShell (Jupyter kernel)
                shell = get_ipython().__class__.__name__
                if shell == "ZMQInteractiveShell":
                    return Environment.JUPYTER

                # Method 4: Check for TerminalInteractiveShell (IPython terminal)
                # This is IPython in terminal, not Jupyter
                if shell == "TerminalInteractiveShell":
                    pass  # Continue to REPL detection

            # Method 5: Check for ipykernel in modules
            import sys

            if "ipykernel" in sys.modules or "ipykernel_launcher" in sys.modules:
                return Environment.JUPYTER

            # Method 6: Check Jupyter environment variables
            import os

            if os.environ.get("JPY_PARENT_PID") or os.environ.get(
                "JUPYTER_RUNTIME_DIR"
            ):
                return Environment.JUPYTER

        except:
            pass

        # Default to REPL for standard Python interpreter
        return Environment.REPL

    @staticmethod
    def get_environment_info() -> dict:
        """
        Get detailed information about the current environment

        Returns:
            Dictionary with environment details
        """
        env = EnvironmentDetector.detect()

        info = {
            "type": env.value,
            "name": env.name,
            "supports_widgets": env in [Environment.COLAB, Environment.JUPYTER],
            "supports_inline_auth": env == Environment.COLAB,
        }

        # Add environment-specific information
        if env == Environment.COLAB:
            info["colab_features"] = {
                "drive_mounted": EnvironmentDetector._is_drive_mounted(),
                "gpu_available": EnvironmentDetector._is_gpu_available(),
            }
        elif env == Environment.JUPYTER:
            info["jupyter_features"] = EnvironmentDetector._get_jupyter_info()

        return info

    @staticmethod
    def _is_drive_mounted() -> bool:
        """Check if Google Drive is mounted in Colab"""
        try:
            import os

            return os.path.exists("/content/drive")
        except:
            return False

    @staticmethod
    def _is_gpu_available() -> bool:
        """Check if GPU is available in the environment"""
        try:
            import torch

            return torch.cuda.is_available()
        except:
            return False

    @staticmethod
    def _get_jupyter_info() -> dict:
        """Get detailed Jupyter environment information"""
        info = {
            "kernel": "unknown",
            "notebook_dir": None,
            "is_notebook": True,
            "is_lab": False,
            "is_classic": False,
        }

        try:
            import os
            import sys

            # Get kernel info
            if "ipykernel" in sys.modules:
                info["kernel"] = "ipykernel"

            # Check if running in JupyterLab vs classic notebook
            if os.environ.get("JUPYTERHUB_SERVICE_PREFIX"):
                info["is_lab"] = True

            # Get notebook directory
            notebook_dir = os.environ.get("JUPYTER_ROOT_DIR") or os.environ.get(
                "NOTEBOOK_ROOT_DIR"
            )
            if notebook_dir:
                info["notebook_dir"] = notebook_dir

            # Check for classic notebook indicators
            if "notebook" in sys.modules:
                info["is_classic"] = True

        except:
            pass

        return info


# Convenience function for quick detection
def detect_environment() -> Environment:
    """Detect the current Python environment"""
    return EnvironmentDetector.detect()
