"""
Unified NotificationMonitor - Simple API for all notification monitoring.

Usage (Notebook):
    from syft_client.notifications import NotificationMonitor

    # One-time setup (creates gmail_token.json from credentials.json)
    NotificationMonitor.setup()

    # Then use in any session
    monitor = NotificationMonitor.from_client(client_do)
    monitor.start()        # Start all (jobs + peers)
    monitor.start("jobs")  # Only job notifications
    monitor.start("peers") # Only peer notifications
    monitor.stop()         # Stop all

Usage (CLI Daemon):
    # Create config file (~/.syft-creds/daemon.yaml):
    #   do_email: "dataowner@example.com"
    #   syftbox_root: "~/SyftBox_dataowner@example.com"
    #   drive_token_path: "~/.syft-creds/token_do.json"
    #   gmail_token_path: "~/.syft-creds/gmail_token.json"

    # Run daemon:
    syft-notify --config ~/.syft-creds/daemon.yaml
"""

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Literal

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftboxManager


# Credential directory detection
COLAB_DRIVE_PATH = Path("/content/drive/MyDrive")
CREDS_DIR_NAME = "syft-creds"


def get_creds_dir() -> Path:
    """
    Get the credentials directory path.

    Returns:
        - Colab/Drive mounted: /content/drive/MyDrive/syft-creds/
        - Local/VM: ~/.syft-creds/
    """
    # Check if Drive is mounted (Colab or manual mount)
    drive_creds = COLAB_DRIVE_PATH / CREDS_DIR_NAME
    if COLAB_DRIVE_PATH.exists():
        return drive_creds

    # Fallback to local home directory
    return Path.home() / f".{CREDS_DIR_NAME}"


def get_credentials_path() -> Path:
    """Get path to credentials.json (OAuth client secrets)."""
    return get_creds_dir() / "credentials.json"


def get_gmail_token_path() -> Path:
    """Get path to gmail_token.json."""
    return get_creds_dir() / "gmail_token.json"


def get_state_path() -> Path:
    """Get path to notification state file."""
    return get_creds_dir() / "notification_state.json"


MonitorType = Literal["jobs", "peers"]


class NotificationMonitor:
    """
    Unified notification monitor for syft-client.

    Monitors job events (new, approved, executed) and peer events
    (new requests, peer granted) and sends email notifications.

    Setup (one-time):
        >>> NotificationMonitor.setup()

    Usage:
        >>> client_do = sc.login_do(email=email, token_path=token_path)
        >>> monitor = NotificationMonitor.from_client(client_do)
        >>> monitor.start()  # Start monitoring in background
        >>> # ... do work ...
        >>> monitor.stop()
    """

    def __init__(
        self,
        do_email: str,
        syftbox_root: Path,
        drive_token_path: Optional[Path] = None,
        gmail_token_path: Optional[Path] = None,
        state_path: Optional[Path] = None,
        interval: int = 10,
        client: Optional["SyftboxManager"] = None,
    ):
        """
        Initialize NotificationMonitor.

        Args:
            do_email: Data Owner email address
            syftbox_root: Path to SyftBox root directory
            drive_token_path: Path to Google Drive OAuth token (for peer monitoring)
            gmail_token_path: Path to Gmail OAuth token (auto-detected)
            state_path: Path to notification state file (auto-detected)
            interval: Check interval in seconds (default: 10)
            client: Optional SyftboxManager instance (for fallback sync)
        """
        self.do_email = do_email
        self.syftbox_root = Path(syftbox_root).expanduser()
        self.drive_token_path = (
            Path(drive_token_path).expanduser() if drive_token_path else None
        )
        self.gmail_token_path = (
            Path(gmail_token_path).expanduser()
            if gmail_token_path
            else get_gmail_token_path()
        )
        self.state_path = (
            Path(state_path).expanduser() if state_path else get_state_path()
        )
        self.interval = interval
        self.client = client

        self._job_monitor = None
        self._peer_monitor = None
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    @classmethod
    def setup(cls, credentials_path: Optional[str] = None) -> None:
        """
        One-time setup: Run Gmail OAuth and save token.

        This looks for credentials.json in the syft-creds directory,
        runs OAuth flow (opens browser), and saves the resulting token.

        Args:
            credentials_path: Optional override for credentials.json location

        Raises:
            FileNotFoundError: If credentials.json not found with setup instructions

        Example:
            >>> NotificationMonitor.setup()
        """
        creds_dir = get_creds_dir()
        creds_path = (
            Path(credentials_path) if credentials_path else get_credentials_path()
        )
        token_path = get_gmail_token_path()

        # Check if already set up
        if token_path.exists():
            print(f"✅ Gmail token already exists: {token_path}")
            print("   To re-authenticate, delete the token and run setup() again.")
            return

        # Check for credentials directory
        if not creds_dir.exists():
            is_colab = COLAB_DRIVE_PATH.exists()
            if is_colab:
                raise FileNotFoundError(
                    f"Credentials directory not found: {creds_dir}\n\n"
                    "Setup instructions (Colab):\n"
                    "1. Go to Google Drive\n"
                    f"2. Create folder: {CREDS_DIR_NAME}\n"
                    "3. Download credentials.json from Google Cloud Console\n"
                    f"4. Upload credentials.json to: My Drive/{CREDS_DIR_NAME}/\n"
                    "5. Run NotificationMonitor.setup() again"
                )
            else:
                raise FileNotFoundError(
                    f"Credentials directory not found: {creds_dir}\n\n"
                    "Setup instructions (Local):\n"
                    f"1. Create directory: mkdir -p {creds_dir}\n"
                    "2. Download credentials.json from Google Cloud Console\n"
                    f"3. Copy credentials.json to: {creds_dir}/\n"
                    "4. Run NotificationMonitor.setup() again"
                )

        # Check for credentials.json
        if not creds_path.exists():
            raise FileNotFoundError(
                f"credentials.json not found: {creds_path}\n\n"
                "To fix:\n"
                "1. Go to Google Cloud Console → APIs & Services → Credentials\n"
                "2. Create OAuth 2.0 Client ID (Desktop app)\n"
                "3. Download as credentials.json\n"
                f"4. Place it at: {creds_path}\n"
                "5. Run NotificationMonitor.setup() again"
            )

        # Run OAuth flow
        from .gmail_auth import GmailAuth

        print("📧 Setting up Gmail notifications...")
        print(f"   Credentials: {creds_path}")
        print(f"   Token will be saved to: {token_path}")
        print()

        auth = GmailAuth()
        credentials = auth.setup_auth(str(creds_path))

        # Save token
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json())

        print()
        print("✅ Gmail setup complete!")
        print(f"   Token saved: {token_path}")

    @classmethod
    def from_client(
        cls,
        client: "SyftboxManager",
        drive_token_path: Optional[str] = None,
        gmail_token_path: Optional[str] = None,
        interval: int = 10,
    ) -> "NotificationMonitor":
        """
        Create NotificationMonitor from syft-client.

        Args:
            client: SyftboxManager from sc.login_do()
            drive_token_path: Path to Drive token (auto-detected if not provided)
            gmail_token_path: Optional path to Gmail token (auto-detected)
            interval: Check interval in seconds

        Returns:
            Configured NotificationMonitor

        Example:
            >>> client_do = sc.login_do(email=email, token_path=token_path)
            >>> monitor = NotificationMonitor.from_client(client_do)
        """
        if not client.is_do:
            raise ValueError(
                "NotificationMonitor should only run on Data Owner (DO) side."
            )

        # Auto-detect drive token if not provided
        if drive_token_path is None:
            drive_token_path = cls._find_drive_token()

        # Auto-detect gmail token if not provided
        if gmail_token_path is None:
            gmail_token_path = get_gmail_token_path()
            if not gmail_token_path.exists():
                raise FileNotFoundError(
                    f"Gmail token not found: {gmail_token_path}\n\n"
                    "Run setup first:\n"
                    "  from syft_client.notifications import NotificationMonitor\n"
                    "  NotificationMonitor.setup()"
                )

        return cls(
            do_email=client.email,
            syftbox_root=client.syftbox_folder,
            drive_token_path=Path(drive_token_path) if drive_token_path else None,
            gmail_token_path=Path(gmail_token_path) if gmail_token_path else None,
            interval=interval,
            client=client,
        )

    @classmethod
    def from_config(
        cls,
        config_path: str,
        interval: Optional[int] = None,
    ) -> "NotificationMonitor":
        """
        Create NotificationMonitor from YAML config file.

        This is the recommended way to create a monitor for CLI/daemon usage
        without requiring a full SyftboxManager client.

        Args:
            config_path: Path to YAML configuration file
            interval: Override interval from config (optional)

        Config file format:
            do_email: "dataowner@example.com"        # Required
            syftbox_root: "~/SyftBox_dataowner"      # Required
            drive_token_path: "~/.syft-creds/token_do.json"  # Required for Drive polling
            gmail_token_path: "~/.syft-creds/gmail_token.json"  # Optional (auto-detected)
            state_path: "~/.syft-creds/notification_state.json"  # Optional
            interval: 30  # Optional, seconds between checks

        Returns:
            Configured NotificationMonitor

        Example:
            >>> monitor = NotificationMonitor.from_config("~/.syft-creds/daemon.yaml")
            >>> monitor.run()  # Blocking
        """
        import yaml

        config_path = Path(config_path).expanduser()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Validate required fields
        required = ["do_email", "syftbox_root"]
        missing = [k for k in required if k not in config]
        if missing:
            raise ValueError(
                f"Config file missing required fields: {missing}\n"
                f"Config file: {config_path}"
            )

        # Use interval from parameter, config, or default
        check_interval = interval or config.get("interval", 30)

        return cls(
            do_email=config["do_email"],
            syftbox_root=config["syftbox_root"],
            drive_token_path=config.get("drive_token_path"),
            gmail_token_path=config.get("gmail_token_path"),
            state_path=config.get("state_path"),
            interval=check_interval,
        )

    @staticmethod
    def _find_drive_token() -> Optional[Path]:
        """Auto-detect Drive token from standard locations."""
        try:
            from syft_client import CREDENTIALS_DIR

            for token_name in ["token_do.json", "token.json"]:
                token_path = CREDENTIALS_DIR / token_name
                if token_path.exists():
                    return token_path
        except ImportError:
            # CREDENTIALS_DIR not available, skip token search in this location
            pass
        return None

    def _ensure_monitors_initialized(self):
        """Lazy-initialize the underlying monitors."""
        if self._job_monitor is not None:
            return

        # Import here to avoid circular imports
        from .job_monitor import JobMonitor
        from .peer_monitor import PeerMonitor
        from .gmail_auth import GmailAuth
        from .gmail_sender import GmailSender
        from .json_state_manager import JsonStateManager

        # Check for Gmail token
        if not self.gmail_token_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found: {self.gmail_token_path}\n\n"
                "Run setup first:\n"
                "  from syft_client.notifications import NotificationMonitor\n"
                "  NotificationMonitor.setup()"
            )

        # Load credentials and create sender
        auth = GmailAuth()
        credentials = auth.load_credentials(self.gmail_token_path)
        sender = GmailSender(credentials)

        # Create state manager
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = JsonStateManager(self.state_path)

        # Notification config
        config = {
            "notify_on_new_job": True,
            "notify_on_job_approved": True,
            "notify_on_job_executed": True,
            "notify_on_new_peer": True,
            "notify_on_peer_granted": True,
        }

        # Create JobMonitor - polls Drive directly for new jobs, checks local for status
        self._job_monitor = JobMonitor(
            syftbox_root=self.syftbox_root,
            do_email=self.do_email,
            sender=sender,
            state=state,
            config=config,
            drive_token_path=self.drive_token_path,
            client=self.client,
        )

        # Create PeerMonitor - gets its own Drive connection (thread-safe)
        if self.drive_token_path and self.drive_token_path.exists():
            self._peer_monitor = PeerMonitor(
                do_email=self.do_email,
                drive_token_path=self.drive_token_path,
                sender=sender,
                state=state,
                config=config,
            )
        else:
            print("⚠️  Drive token not found. Peer monitoring disabled.")
            print(f"   Expected at: {self.drive_token_path}")
            self._peer_monitor = None

    def start(
        self, monitor_type: Optional[MonitorType] = None
    ) -> "NotificationMonitor":
        """
        Start monitoring in background.

        Args:
            monitor_type: What to monitor - "jobs", "peers", or None for both

        Returns:
            self (for chaining)

        Example:
            >>> monitor.start()        # Start all (jobs + peers)
            >>> monitor.start("jobs")  # Only job notifications
            >>> monitor.start("peers") # Only peer notifications
        """
        self._ensure_monitors_initialized()
        self._stop_event.clear()

        if monitor_type is None or monitor_type == "jobs":
            if self._job_monitor:
                thread = self._job_monitor.start(interval=self.interval)
                self._threads.append(thread)

        if monitor_type is None or monitor_type == "peers":
            if self._peer_monitor:
                thread = self._peer_monitor.start(interval=self.interval)
                self._threads.append(thread)
            elif monitor_type == "peers":
                print("⚠️  Peer monitoring not available (Drive token not found)")

        return self

    def stop(self) -> None:
        """Stop all monitoring."""
        if self._job_monitor:
            self._job_monitor.stop()
        if self._peer_monitor:
            self._peer_monitor.stop()
        self._threads.clear()

    def check(self, monitor_type: Optional[MonitorType] = None) -> None:
        """
        Run a single check (non-blocking).

        Args:
            monitor_type: What to check - "jobs", "peers", or None for both
        """
        self._ensure_monitors_initialized()

        if monitor_type is None or monitor_type == "jobs":
            if self._job_monitor:
                self._job_monitor.check()

        if monitor_type is None or monitor_type == "peers":
            if self._peer_monitor:
                self._peer_monitor.check()

    def notify_peer_granted(self, ds_email: str) -> None:
        """
        Notify DS that their peer request was accepted.

        Call this after DO runs add_peer(ds_email).

        Args:
            ds_email: Data Scientist email
        """
        self._ensure_monitors_initialized()
        if self._peer_monitor:
            self._peer_monitor.notify_peer_granted(ds_email)

    @property
    def is_running(self) -> bool:
        """Check if any monitors are running."""
        return any(t.is_alive() for t in self._threads)

    def run(self, monitor_type: Optional[MonitorType] = None) -> None:
        """
        Run monitoring in foreground (blocking).

        This is the main entry point for CLI/daemon usage. It runs until
        interrupted with Ctrl+C or SIGTERM.

        Args:
            monitor_type: What to monitor - "jobs", "peers", or None for both

        Example:
            >>> monitor = NotificationMonitor.from_config("daemon.yaml")
            >>> monitor.run()  # Blocks until Ctrl+C
        """
        self._ensure_monitors_initialized()
        self._stop_event.clear()

        print("🔔 Starting notification daemon...")
        print(f"   DO: {self.do_email}")
        print(f"   SyftBox: {self.syftbox_root}")
        print(f"   Interval: {self.interval}s")
        print("   Press Ctrl+C to stop")
        print()

        monitors_started = []
        if monitor_type is None or monitor_type == "jobs":
            if self._job_monitor:
                monitors_started.append("JobMonitor")
                print("🔔 JobMonitor started")
        if monitor_type is None or monitor_type == "peers":
            if self._peer_monitor:
                monitors_started.append("PeerMonitor")
                print("🔔 PeerMonitor started")
            elif monitor_type == "peers":
                print("⚠️  PeerMonitor not available (Drive token not found)")

        if not monitors_started:
            print("❌ No monitors could be started. Check your configuration.")
            return

        print()

        try:
            while not self._stop_event.is_set():
                # Run checks
                if monitor_type is None or monitor_type == "jobs":
                    if self._job_monitor:
                        try:
                            self._job_monitor._check_all_entities()
                        except Exception as e:
                            print(f"⚠️  JobMonitor error: {e}")

                if monitor_type is None or monitor_type == "peers":
                    if self._peer_monitor:
                        try:
                            self._peer_monitor._check_all_entities()
                        except Exception as e:
                            print(f"⚠️  PeerMonitor error: {e}")

                # Wait for next interval
                self._stop_event.wait(self.interval)

        except KeyboardInterrupt:
            print("\n⏹️  Shutting down...")

        self._stop_event.set()
        print("✅ Notification daemon stopped")

    @staticmethod
    def get_creds_dir() -> Path:
        """Get the credentials directory path (for user reference)."""
        return get_creds_dir()
