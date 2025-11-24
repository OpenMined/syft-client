"""
Helper functions for easy notification setup.

Provides high-level API for quick setup of the notification system.
"""

import yaml
from pathlib import Path

try:
    from .gmail_auth import GmailAuth
    from .job_monitor import JobMonitor
except ImportError:
    from gmail_auth import GmailAuth
    from job_monitor import JobMonitor


def setup_oauth(config_path: str) -> None:
    """
    One-time OAuth setup helper.

    Opens browser for Gmail authentication and saves token.
    This needs to be run only once before starting monitoring.

    Args:
        config_path: Path to YAML config file

    Raises:
        FileNotFoundError: If config file or credentials file not found
        ValueError: If config is missing required keys

    Example:
        >>> setup_oauth("notification_config.yaml")
        🔐 Starting OAuth flow...
           Browser will open shortly
           Sign in and grant Gmail send permissions
        ✅ OAuth complete!
        ✅ Token saved to: ~/.syftbox/notifications/gmail_token.json
    """
    config_path = Path(config_path).expanduser()

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Please create a notification_config.yaml file.\n"
            "See: syft_client/notifications/README.md for example"
        )

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    required_keys = ["credentials_file", "token_file"]
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(
            f"Configuration missing required keys for OAuth: {missing}\n"
            f"Config file: {config_path}"
        )

    credentials_file = Path(config["credentials_file"]).expanduser()
    token_file = Path(config["token_file"]).expanduser()

    if not credentials_file.exists():
        raise FileNotFoundError(
            f"credentials.json not found at: {credentials_file}\n\n"
            "To get credentials.json:\n"
            "1. Go to: https://console.cloud.google.com/apis/credentials\n"
            "2. Create a new project (or select existing)\n"
            "3. Enable Gmail API\n"
            "4. Create OAuth 2.0 Client ID (Desktop app)\n"
            "5. Download as credentials.json\n"
            f"6. Save to: {credentials_file}"
        )

    if token_file.exists():
        print(f"✅ Token already exists at: {token_file}")
        print("   Delete this file to re-authenticate")
        return

    # TODO: Replace print statements with proper logging
    # logger.info("Starting OAuth flow...")
    print("🔐 Starting OAuth flow...")
    print("   Browser will open shortly")
    print("   Sign in and grant Gmail send permissions")
    print()

    auth = GmailAuth()
    credentials = auth.setup_auth(credentials_file)

    token_file.parent.mkdir(parents=True, exist_ok=True)
    with open(token_file, "w") as f:
        f.write(credentials.to_json())
    token_file.chmod(0o600)

    print()
    print("✅ OAuth complete!")
    print(f"✅ Token saved to: {token_file}")
    print()
    print("Next steps:")
    print("  from syft_client.notifications import start_monitoring")
    print(f'  monitor = start_monitoring("{config_path}")')
    print("  monitor.check(interval=10)  # Check every 10 seconds")


def start_monitoring(config_path: str) -> JobMonitor:
    """
    Create and return configured JobMonitor.

    Loads configuration from YAML file and creates a ready-to-use monitor.

    Args:
        config_path: Path to YAML config file

    Returns:
        Configured JobMonitor instance ready to use

    Raises:
        FileNotFoundError: If config or token file not found
        ValueError: If config is missing required keys

    Example:
        >>> monitor = start_monitoring("notification_config.yaml")
        >>> monitor.check()                         # Single check
        >>> monitor.check(interval=10)              # Every 10s forever
        >>> monitor.check(interval=10, duration=3600)  # Run for 1 hour
    """
    config_path = Path(config_path).expanduser()

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            "Please create a notification_config.yaml file.\n"
            "See: syft_client/notifications/README.md for example"
        )

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    if "token_file" not in config:
        raise ValueError(
            f"Configuration missing 'token_file' key\nConfig file: {config_path}"
        )

    token_file = Path(config["token_file"]).expanduser()

    if not token_file.exists():
        raise FileNotFoundError(
            f"OAuth token not found at: {token_file}\n\n"
            "Run setup_oauth() first:\n"
            "  from syft_client.notifications import setup_oauth\n"
            f'  setup_oauth("{config_path}")\n\n'
            "This will open a browser for Gmail authentication."
        )

    return JobMonitor.from_config(str(config_path))
