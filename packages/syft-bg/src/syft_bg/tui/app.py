"""TUI dashboard for SyftBox background services."""

import re
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

from syft_bg.services import ServiceManager, ServiceStatus


class ServiceCard(Static):
    """Widget displaying a single service's status."""

    DEFAULT_CSS = """
    ServiceCard {
        width: 100%;
        height: auto;
        padding: 1 2;
        margin: 0 0 1 0;
        background: $surface;
        border: solid $primary;
    }

    ServiceCard.running {
        border: solid $success;
    }

    ServiceCard.stopped {
        border: solid $surface-lighten-2;
    }

    ServiceCard.error {
        border: solid $error;
    }

    ServiceCard:focus {
        border: double $accent;
    }

    .service-header {
        width: 100%;
    }

    .service-name {
        text-style: bold;
        width: auto;
    }

    .service-status {
        width: auto;
        margin-left: 2;
    }

    .service-status.running {
        color: $success;
    }

    .service-status.stopped {
        color: $text-muted;
    }

    .service-status.error {
        color: $error;
    }

    .service-desc {
        color: $text-muted;
        margin-top: 1;
    }

    .service-pid {
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("enter", "toggle", "Start/Stop"),
        Binding("r", "restart", "Restart"),
        Binding("l", "logs", "Logs"),
    ]

    can_focus = True

    def __init__(self, service_name: str, **kwargs):
        super().__init__(**kwargs)
        self.service_name = service_name
        self.manager = ServiceManager()

    def compose(self) -> ComposeResult:
        service = self.manager.get_service(self.service_name)
        info = service.get_status()

        status_text = self._get_status_text(info.status)
        status_class = self._get_status_class(info.status)
        pid_text = f"PID: {info.pid}" if info.pid else ""

        with Horizontal(classes="service-header"):
            yield Static(self.service_name.upper(), classes="service-name")
            yield Static(
                f"● {status_text}"
                if info.status == ServiceStatus.RUNNING
                else f"○ {status_text}",
                classes=f"service-status {status_class}",
                id=f"status-{self.service_name}",
            )
            yield Static(pid_text, classes="service-pid", id=f"pid-{self.service_name}")

        yield Static(service.description, classes="service-desc")

    def _get_status_text(self, status: ServiceStatus) -> str:
        return {
            ServiceStatus.RUNNING: "Running",
            ServiceStatus.STOPPED: "Stopped",
            ServiceStatus.ERROR: "Error",
        }.get(status, "Unknown")

    def _get_status_class(self, status: ServiceStatus) -> str:
        return {
            ServiceStatus.RUNNING: "running",
            ServiceStatus.STOPPED: "stopped",
            ServiceStatus.ERROR: "error",
        }.get(status, "")

    def refresh_status(self):
        """Update the service status display."""
        service = self.manager.get_service(self.service_name)
        info = service.get_status()

        status_text = self._get_status_text(info.status)
        status_class = self._get_status_class(info.status)

        # Update status widget
        status_widget = self.query_one(f"#status-{self.service_name}", Static)
        icon = "●" if info.status == ServiceStatus.RUNNING else "○"
        status_widget.update(f"{icon} {status_text}")
        status_widget.set_classes(f"service-status {status_class}")

        # Update PID widget
        pid_widget = self.query_one(f"#pid-{self.service_name}", Static)
        pid_widget.update(f"PID: {info.pid}" if info.pid else "")

        # Update card border
        self.set_classes(status_class)

    def action_toggle(self):
        """Toggle service start/stop."""
        service = self.manager.get_service(self.service_name)
        info = service.get_status()

        if info.status == ServiceStatus.RUNNING:
            success, msg = service.stop()
        else:
            success, msg = service.start()

        self.app.notify(msg, severity="information" if success else "error")
        self.refresh_status()

    def action_restart(self):
        """Restart the service."""
        service = self.manager.get_service(self.service_name)
        success, msg = service.restart()
        self.app.notify(msg, severity="information" if success else "error")
        self.refresh_status()

    def action_logs(self):
        """Show logs for this service."""
        self.app.push_screen(LogScreen(self.service_name))


class ActivityFeed(Static):
    """Widget showing recent activity from all services."""

    DEFAULT_CSS = """
    ActivityFeed {
        width: 100%;
        height: 100%;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }

    .activity-title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }

    .activity-content {
        width: 100%;
        height: 100%;
        overflow-y: auto;
    }

    .activity-line {
        width: 100%;
    }

    .activity-line.notify {
        color: $primary;
    }

    .activity-line.approve {
        color: $success;
    }

    .activity-line.error {
        color: $error;
    }

    .activity-line.info {
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.manager = ServiceManager()

    def compose(self) -> ComposeResult:
        yield Static("📋 ACTIVITY FEED", classes="activity-title")
        yield ScrollableContainer(
            Static(self._get_activity_text(), id="activity-text"),
            classes="activity-content",
        )

    def _get_activity_text(self) -> str:
        """Get recent activity from all service logs."""
        all_entries = []

        for service_name in self.manager.list_services():
            logs = self.manager.get_logs(service_name, lines=20)
            for line in logs:
                # Parse timestamp and add service tag
                entry = self._parse_log_line(service_name, line)
                if entry:
                    all_entries.append(entry)

        # Sort by timestamp, most recent first
        all_entries.sort(key=lambda x: x[0], reverse=True)

        if not all_entries:
            return "No activity yet. Start services to see activity."

        # Format entries
        lines = []
        for timestamp, service, message in all_entries[:30]:
            time_str = timestamp.strftime("%H:%M:%S") if timestamp else "??:??:??"
            tag = self._get_service_tag(service)
            lines.append(f"{time_str} {tag} {message}")

        return "\n".join(lines)

    def _parse_log_line(self, service: str, line: str) -> tuple | None:
        """Parse a log line into (timestamp, service, message)."""
        if not line.strip():
            return None

        # Try to extract timestamp (common formats)
        timestamp = None
        message = line

        # Match ISO format: 2024-01-15 10:30:45
        iso_match = re.match(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
        if iso_match:
            try:
                timestamp = datetime.strptime(iso_match.group(1), "%Y-%m-%d %H:%M:%S")
                message = line[iso_match.end() :].strip(" -:")
            except ValueError:
                pass

        # Match time only: 10:30:45
        time_match = re.match(r"(\d{2}:\d{2}:\d{2})", line)
        if not timestamp and time_match:
            try:
                today = datetime.now().date()
                time_part = datetime.strptime(time_match.group(1), "%H:%M:%S").time()
                timestamp = datetime.combine(today, time_part)
                message = line[time_match.end() :].strip(" -:")
            except ValueError:
                pass

        if not timestamp:
            timestamp = datetime.now()

        return (timestamp, service, message)

    def _get_service_tag(self, service: str) -> str:
        """Get a formatted tag for the service."""
        tags = {
            "notify": "[📧]",
            "approve": "[✅]",
        }
        return tags.get(service, f"[{service}]")

    def refresh_activity(self):
        """Refresh the activity feed."""
        try:
            text_widget = self.query_one("#activity-text", Static)
            text_widget.update(self._get_activity_text())
        except Exception:
            pass


class LogScreen(ModalScreen):
    """Screen showing logs for a service."""

    DEFAULT_CSS = """
    LogScreen {
        align: center middle;
    }

    #log-dialog {
        width: 90%;
        height: 90%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    .log-header {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }

    .log-content {
        width: 100%;
        height: 100%;
        overflow-y: auto;
        background: $background;
        padding: 1;
    }

    .log-hint {
        margin-top: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("q", "pop_screen", "Back"),
    ]

    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name
        self.manager = ServiceManager()

    def compose(self) -> ComposeResult:
        logs = self.manager.get_logs(self.service_name, lines=100)
        log_text = "\n".join(logs) if logs else "No logs available"

        with Container(id="log-dialog"):
            yield Static(f"📄 LOGS: {self.service_name.upper()}", classes="log-header")
            yield ScrollableContainer(
                Static(log_text, classes="log-text"),
                classes="log-content",
            )
            yield Static("Press ESC or q to close", classes="log-hint")

    def action_pop_screen(self):
        self.app.pop_screen()


class SyftBgApp(App):
    """TUI dashboard for SyftBox background services."""

    TITLE = "SyftBox Background Services"
    SUB_TITLE = "Press ? for help"

    CSS = """
    Screen {
        background: $background;
    }

    #main-container {
        width: 100%;
        height: 100%;
        padding: 1 2;
    }

    #top-row {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    #services-column {
        width: 1fr;
        height: auto;
    }

    .title {
        text-style: bold;
        margin-bottom: 1;
        color: $primary;
    }

    #activity-container {
        width: 100%;
        height: 1fr;
        min-height: 10;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $surface;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("a", "start_all", "Start All"),
        Binding("x", "stop_all", "Stop All"),
        Binding("R", "refresh", "Refresh"),
        Binding("i", "init", "Init"),
    ]

    def __init__(self):
        super().__init__()
        self.manager = ServiceManager()

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Horizontal(id="top-row"):
                with Vertical(id="services-column"):
                    yield Static("🔧 SERVICES", classes="title")
                    for service_name in self.manager.list_services():
                        yield ServiceCard(service_name, id=f"card-{service_name}")
            with Container(id="activity-container"):
                yield ActivityFeed(id="activity-feed")
        yield Footer()

    def action_start_all(self):
        """Start all services."""
        results = self.manager.start_all()
        for name, (success, msg) in results.items():
            self.notify(
                f"{name}: {msg}", severity="information" if success else "error"
            )
        self._refresh_all()

    def action_stop_all(self):
        """Stop all services."""
        results = self.manager.stop_all()
        for name, (success, msg) in results.items():
            self.notify(
                f"{name}: {msg}", severity="information" if success else "error"
            )
        self._refresh_all()

    def action_refresh(self):
        """Refresh all service statuses."""
        self._refresh_all()
        self.notify("Status refreshed")

    def action_init(self):
        """Run the init flow (exits TUI first)."""
        self.exit(return_code=2)  # Special code for init

    def action_help(self):
        """Show help."""
        help_text = """
Keyboard Shortcuts:
  ↑/↓   - Navigate services
  Enter - Start/Stop selected service
  r     - Restart selected service
  l     - View service logs
  a     - Start all services
  x     - Stop all services
  R     - Refresh status
  i     - Run init setup
  q     - Quit
        """
        self.notify(help_text.strip(), timeout=10)

    def _refresh_all(self):
        """Refresh status of all service cards and activity feed."""
        for service_name in self.manager.list_services():
            card = self.query_one(f"#card-{service_name}", ServiceCard)
            card.refresh_status()

        try:
            feed = self.query_one("#activity-feed", ActivityFeed)
            feed.refresh_activity()
        except Exception:
            pass

    def on_mount(self):
        """Set up auto-refresh timer."""
        self.set_interval(5, self._refresh_all)


def run_tui():
    """Run the TUI dashboard."""
    app = SyftBgApp()
    result = app.run()

    # Handle special exit codes
    if result == 2:
        from syft_bg.cli.init_flow import run_init_flow

        run_init_flow()
