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
        
        # Check for Jupyter/IPython
        try:
            get_ipython = __builtins__.get('get_ipython', None)
            if get_ipython is not None:
                if 'IPKernelApp' in get_ipython().config:
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
        
        return info
    
    @staticmethod
    def _is_drive_mounted() -> bool:
        """Check if Google Drive is mounted in Colab"""
        try:
            import os
            return os.path.exists('/content/drive')
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


# Convenience function for quick detection
def detect_environment() -> Environment:
    """Detect the current Python environment"""
    return EnvironmentDetector.detect()