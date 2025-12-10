"""
SyftBox Notification System

Email notifications for SyftBox events using Gmail.

Quick Start
-----------
    from syft_client.notifications import NotificationMonitor

    # Start monitoring (requires Gmail token at ~/.syft-notifications/gmail_token.json)
    monitor = NotificationMonitor.from_client(client_do)
    monitor.start()        # Start all (jobs + peers)
    monitor.start("jobs")  # Only job notifications
    monitor.start("peers") # Only peer notifications
    monitor.stop()         # Stop all

Gmail Setup (one-time)
----------------------
    from syft_client.notifications import GmailAuth

    auth = GmailAuth()
    creds = auth.setup_auth("path/to/credentials.json")

    # Save token
    from pathlib import Path
    token_path = Path.home() / ".syft-notifications" / "gmail_token.json"
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json())

Notification Types
------------------
Jobs:
- New Job → Email to Data Owner when job arrives
- Job Approved → Email to Data Scientist when approved
- Job Executed → Email to Data Scientist when complete

Peers:
- New Peer Request → Email to Data Owner when DS adds them
- Peer Added → Email to DS when DO adds them back
- Peer Granted → Email to DS when mutual peering established
"""

# High-level API (recommended)
from .monitor import NotificationMonitor

# Core components (advanced usage)
from .gmail_auth import GmailAuth
from .gmail_sender import GmailSender
from .json_state_manager import JsonStateManager
from .job_monitor import JobMonitor
from .peer_monitor import PeerMonitor
from .template_renderer import TemplateRenderer

# Abstract base classes (for extensions)
from .base import Monitor, NotificationSender, StateManager, AuthProvider

__all__ = [
    # High-level API
    "NotificationMonitor",
    # Core components
    "GmailAuth",
    "GmailSender",
    "JsonStateManager",
    "JobMonitor",
    "PeerMonitor",
    "TemplateRenderer",
    # Abstract bases
    "Monitor",
    "NotificationSender",
    "StateManager",
    "AuthProvider",
]

__version__ = "0.1.0"
