"""
Token storage with OS keyring support and pickle fallback
"""

import pickle
from pathlib import Path
from typing import Optional

from .constants import (
    CONFIG_DIR_NAME,
    TOKEN_FILE_NAME,
    KEYRING_SERVICE,
    KEYRING_TOKEN_KEY,
)


def get_config_dir() -> Path:
    """Get or create config directory"""
    config_dir = Path.home() / CONFIG_DIR_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def save_token(token_dict: dict) -> str:
    """
    Save token to secure storage

    Returns:
        Storage method used: 'keyring' or 'file'
    """
    # Try keyring first (most secure)
    try:
        import keyring
        import json

        keyring.set_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY, json.dumps(token_dict))
        return "keyring"
    except Exception:
        # Fallback to pickle file
        token_file = get_config_dir() / TOKEN_FILE_NAME
        with open(token_file, "wb") as f:
            pickle.dump(token_dict, f)
        # Set secure permissions (owner only)
        token_file.chmod(0o600)
        return "file"


def load_token() -> Optional[dict]:
    """
    Load token from secure storage

    Returns:
        Token dict if found, None otherwise
    """
    # Try keyring first
    try:
        import keyring
        import json

        token_json = keyring.get_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
        if token_json:
            return json.loads(token_json)
    except Exception:
        pass

    # Fallback to pickle file
    token_file = get_config_dir() / TOKEN_FILE_NAME
    if token_file.exists():
        with open(token_file, "rb") as f:
            return pickle.load(f)

    return None


def clear_token():
    """Clear stored token from all locations"""
    # Clear from keyring
    try:
        import keyring

        keyring.delete_password(KEYRING_SERVICE, KEYRING_TOKEN_KEY)
    except Exception:
        pass

    # Clear from file
    token_file = get_config_dir() / TOKEN_FILE_NAME
    if token_file.exists():
        token_file.unlink()
