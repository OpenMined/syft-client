"""
SyftBox Notification System

Email notifications for SyftBox job events using Gmail.

Quick Start
-----------
    from syft_client.notifications import setup_oauth, start_monitoring

    # One-time setup (opens browser for authentication)
    setup_oauth("notification_config.yaml")

    # Start monitoring
    monitor = start_monitoring("notification_config.yaml")
    monitor.check(interval=10)  # Check every 10 seconds

Notification Types
------------------
1. New Job → Email to Data Owner when job arrives
2. Job Approved → Email to Data Scientist when job approved
3. Job Executed → Email to Data Scientist when job completes

Architecture
------------
The system uses abstract base classes for extensibility:
- Monitor(ABC) - Base for job/peer monitoring
- NotificationSender(ABC) - Base for email/slack/discord senders
- StateManager(ABC) - Base for JSON/SQLite/Redis state tracking
- AuthProvider(ABC) - Base for OAuth/API key authentication

Advanced Usage
--------------
For direct control over components:

    from syft_client.notifications import (
        GmailAuth, GmailSender, JsonStateManager, JobMonitor
    )

    # Manual setup
    auth = GmailAuth()
    credentials = auth.load_credentials("token.json")
    sender = GmailSender(credentials)
    state = JsonStateManager("state.json")

    monitor = JobMonitor(
        syftbox_root="~/SyftBox",
        do_email="owner@example.com",
        sender=sender,
        state=state,
        config={"notify_on_new_job": True}
    )

See Also
--------
- README.md in this directory for detailed documentation
- notification_config.yaml for configuration example
"""

# High-level API (recommended)
from .helpers import setup_oauth, start_monitoring

# Core components (advanced usage)
from .gmail_auth import GmailAuth
from .gmail_sender import GmailSender
from .json_state_manager import JsonStateManager
from .job_monitor import JobMonitor

# Abstract base classes (for extensions)
from .base import Monitor, NotificationSender, StateManager, AuthProvider

__all__ = [
    # High-level API
    "setup_oauth",
    "start_monitoring",
    # Core components
    "GmailAuth",
    "GmailSender",
    "JsonStateManager",
    "JobMonitor",
    # Abstract bases
    "Monitor",
    "NotificationSender",
    "StateManager",
    "AuthProvider",
]

__version__ = "0.1.0"
