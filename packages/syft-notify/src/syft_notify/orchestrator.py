import threading
from pathlib import Path
from typing import Literal, Optional

from syft_notify.core.config import NotifyConfig, get_default_paths
from syft_notify.gmail import GmailAuth, GmailSender
from syft_notify.handlers import JobHandler, PeerHandler
from syft_notify.monitors import JobMonitor, PeerMonitor
from syft_notify.state import JsonStateManager

MonitorType = Literal["jobs", "peers"]


class NotificationOrchestrator:
    def __init__(
        self,
        do_email: str,
        syftbox_root: Path,
        drive_token_path: Optional[Path] = None,
        gmail_token_path: Optional[Path] = None,
        state_path: Optional[Path] = None,
        interval: int = 30,
    ):
        self.do_email = do_email
        self.syftbox_root = Path(syftbox_root).expanduser()
        self.interval = interval

        paths = get_default_paths()
        self.drive_token_path = (
            Path(drive_token_path).expanduser()
            if drive_token_path
            else paths["drive_token"]
        )
        self.gmail_token_path = (
            Path(gmail_token_path).expanduser()
            if gmail_token_path
            else paths["gmail_token"]
        )
        self.state_path = (
            Path(state_path).expanduser() if state_path else paths["state"]
        )

        self._job_monitor: Optional[JobMonitor] = None
        self._peer_monitor: Optional[PeerMonitor] = None
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

    @classmethod
    def setup(cls, credentials_path: Optional[str] = None) -> None:
        paths = get_default_paths()
        creds_path = (
            Path(credentials_path) if credentials_path else paths["credentials"]
        )
        token_path = paths["gmail_token"]

        if token_path.exists():
            print(f"✅ Gmail token already exists: {token_path}")
            return

        if not creds_path.exists():
            raise FileNotFoundError(
                f"credentials.json not found: {creds_path}\n\n"
                "Download from Google Cloud Console and place at this path."
            )

        print("📧 Setting up Gmail notifications...")
        auth = GmailAuth()
        credentials = auth.setup_auth(creds_path)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json())

        print(f"✅ Gmail token saved: {token_path}")

    @classmethod
    def from_client(
        cls,
        client,
        gmail_token_path: Optional[str] = None,
        interval: int = 30,
    ) -> "NotificationOrchestrator":
        if not client.is_do:
            raise ValueError(
                "NotificationOrchestrator should only run on Data Owner (DO) side."
            )

        paths = get_default_paths()

        gmail_path = (
            Path(gmail_token_path).expanduser()
            if gmail_token_path
            else paths["gmail_token"]
        )
        if not gmail_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found: {gmail_path}\n\n"
                "Run NotificationOrchestrator.setup() first."
            )

        drive_token_path = cls._find_drive_token()

        return cls(
            do_email=client.email,
            syftbox_root=client.syftbox_folder,
            drive_token_path=drive_token_path,
            gmail_token_path=gmail_path,
            interval=interval,
        )

    @staticmethod
    def _find_drive_token() -> Optional[Path]:
        try:
            from syft_client import CREDENTIALS_DIR

            for token_name in ["token_do.json", "token.json"]:
                token_path = CREDENTIALS_DIR / token_name
                if token_path.exists():
                    return token_path
        except ImportError:
            pass

        paths = get_default_paths()
        if paths["drive_token"].exists():
            return paths["drive_token"]

        return None

    @classmethod
    def from_config(
        cls,
        config_path: Optional[str] = None,
        interval: Optional[int] = None,
    ) -> "NotificationOrchestrator":
        config = NotifyConfig.load(Path(config_path) if config_path else None)

        if not config.do_email:
            raise ValueError("Config missing 'email' field")
        if not config.syftbox_root:
            raise ValueError("Config missing 'syftbox_root' field")

        return cls(
            do_email=config.do_email,
            syftbox_root=config.syftbox_root,
            drive_token_path=config.drive_token_path,
            gmail_token_path=config.gmail_token_path,
            interval=interval or config.interval,
        )

    def _ensure_initialized(self):
        if self._job_monitor is not None:
            return

        if not self.gmail_token_path.exists():
            raise FileNotFoundError(
                f"Gmail token not found: {self.gmail_token_path}\n\n"
                "Run NotificationOrchestrator.setup() first."
            )

        auth = GmailAuth()
        credentials = auth.load_credentials(self.gmail_token_path)
        sender = GmailSender(credentials)

        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        state = JsonStateManager(self.state_path)

        job_handler = JobHandler(sender, state)
        peer_handler = PeerHandler(sender, state)

        self._job_monitor = JobMonitor(
            syftbox_root=self.syftbox_root,
            do_email=self.do_email,
            handler=job_handler,
            state=state,
            drive_token_path=self.drive_token_path,
        )

        # Create peer monitor if we have a token file OR if we're in Colab (native auth)
        from syft_notify.core.base import is_colab

        if is_colab() or (self.drive_token_path and self.drive_token_path.exists()):
            self._peer_monitor = PeerMonitor(
                do_email=self.do_email,
                drive_token_path=self.drive_token_path,
                handler=peer_handler,
                state=state,
            )

    def start(
        self, monitor_type: Optional[MonitorType] = None
    ) -> "NotificationOrchestrator":
        self._ensure_initialized()
        self._stop_event.clear()

        if monitor_type is None or monitor_type == "jobs":
            if self._job_monitor:
                thread = self._job_monitor.start(interval=self.interval)
                self._threads.append(thread)

        if monitor_type is None or monitor_type == "peers":
            if self._peer_monitor:
                thread = self._peer_monitor.start(interval=self.interval)
                self._threads.append(thread)

        return self

    def stop(self) -> None:
        if self._job_monitor:
            self._job_monitor.stop()
        if self._peer_monitor:
            self._peer_monitor.stop()
        self._threads.clear()

    def check(self, monitor_type: Optional[MonitorType] = None) -> None:
        self._ensure_initialized()

        if monitor_type is None or monitor_type == "jobs":
            if self._job_monitor:
                self._job_monitor.check()

        if monitor_type is None or monitor_type == "peers":
            if self._peer_monitor:
                self._peer_monitor.check()

    def notify_peer_granted(self, ds_email: str) -> None:
        self._ensure_initialized()
        if self._peer_monitor:
            self._peer_monitor.notify_peer_granted(ds_email)

    @property
    def is_running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    def run(self, monitor_type: Optional[MonitorType] = None) -> None:
        self._ensure_initialized()
        self._stop_event.clear()

        print("🔔 Starting notification daemon...")
        print(f"   DO: {self.do_email}")
        print(f"   SyftBox: {self.syftbox_root}")
        print(f"   Interval: {self.interval}s")
        print()

        try:
            while not self._stop_event.is_set():
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

                self._stop_event.wait(self.interval)

        except KeyboardInterrupt:
            print("\n⏹️  Shutting down...")

        self._stop_event.set()
        print("✅ Notification daemon stopped")
