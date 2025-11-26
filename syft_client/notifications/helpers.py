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


# Default paths for package-managed files
DEFAULT_NOTIFICATION_DIR = Path.home() / ".syft-notifications"
DEFAULT_TOKEN_FILE = DEFAULT_NOTIFICATION_DIR / "gmail_token.json"
DEFAULT_STATE_FILE = DEFAULT_NOTIFICATION_DIR / "state.json"


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

    # Only credentials_file is required from user
    if "credentials_file" not in config:
        raise ValueError(
            f"Configuration missing required key: 'credentials_file'\n"
            f"Config file: {config_path}\n"
            "Please specify path to your Google OAuth credentials.json file"
        )

    credentials_file = Path(config["credentials_file"]).expanduser()

    # Use default token_file if not specified
    if "token_file" in config:
        token_file = Path(config["token_file"]).expanduser()
    else:
        token_file = DEFAULT_TOKEN_FILE
        print(f"ℹ️  Using default token location: {token_file}")

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

    # Use default token_file if not specified
    if "token_file" in config:
        token_file = Path(config["token_file"]).expanduser()
    else:
        token_file = DEFAULT_TOKEN_FILE

    if not token_file.exists():
        raise FileNotFoundError(
            f"OAuth token not found at: {token_file}\n\n"
            "Run setup_oauth() first:\n"
            "  from syft_client.notifications import setup_oauth\n"
            f'  setup_oauth("{config_path}")\n\n'
            "This will open a browser for Gmail authentication."
        )

    # Inject default paths into config if not present
    if "token_file" not in config:
        config["token_file"] = str(token_file)
    if "state_file" not in config:
        config["state_file"] = str(DEFAULT_STATE_FILE)

    return JobMonitor.from_config(str(config_path))
