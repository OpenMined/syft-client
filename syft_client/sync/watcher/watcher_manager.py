"""
Client-side watcher management
"""

from typing import Any, Dict, List, Optional

import requests

from .file_watcher import create_watcher_endpoint, destroy_watcher_endpoint


class WatcherManager:
    """Manages file watchers for the client"""

    def __init__(self, client):
        self.client = client
        self._server = None
        self._server_name = (
            f"watcher_sender_{client.email.replace('@', '_at_').replace('.', '_')}"
        )

    def start(
        self,
        paths: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
        bidirectional: bool = True,
        check_interval: int = 30,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Start the file watcher"""
        # For now, we ignore custom paths/patterns as they would need to be
        # passed through syft-serve, which is more complex
        # Future enhancement: pass config through environment variables

        if self.is_running():
            return {
                "status": "already_running",
                "message": f"Watcher already active for {self.client.email}",
            }

        # Create and start the watcher endpoint
        self._server = create_watcher_endpoint(self.client.email, verbose=verbose)

        return {
            "status": "started",
            "message": f"Watcher started for {self.client.email}",
        }

    def stop(self, verbose: bool = True) -> bool:
        """Stop the file watcher"""
        success = destroy_watcher_endpoint(self.client.email, verbose=verbose)
        if success:
            self._server = None
        return success

    def is_running(self) -> bool:
        """Check if watcher is running"""
        try:
            import syft_serve as ss

            existing_servers = list(ss.servers)
            for server in existing_servers:
                if server.name == self._server_name:
                    # Try to ping the server
                    try:
                        response = requests.get(f"{server.url}/health", timeout=2)
                        return response.status_code == 200
                    except:
                        # Server exists but not responding
                        return False
            return False
        except ImportError:
            return False

    def status(self) -> Dict[str, Any]:
        """Get watcher status"""
        if not self.is_running():
            return {"running": False, "message": "Watcher not running"}

        try:
            import syft_serve as ss

            for server in ss.servers:
                if server.name == self._server_name:
                    return {
                        "running": True,
                        "server_url": server.url,
                        "server_name": server.name,
                        "email": self.client.email,
                        "message": f"Watcher active for {self.client.email}",
                    }
        except:
            pass

        return {"running": False, "message": "Unable to get watcher status"}

    def list_all(self) -> List[Dict[str, Any]]:
        """List all active watchers across all emails"""
        watchers = []
        try:
            import syft_serve as ss

            for server in ss.servers:
                if server.name.startswith("watcher_sender_"):
                    # Extract email from server name
                    email_part = server.name.replace("watcher_sender_", "")
                    email = email_part.replace("_at_", "@").replace("_", ".")

                    watchers.append(
                        {
                            "email": email,
                            "server_name": server.name,
                            "server_url": server.url,
                            "running": True,
                        }
                    )
        except ImportError:
            pass

        return watchers

    def get_history(self, file_path: str, limit: int = 10) -> List[Dict]:
        """Get sync history for a file"""
        # This would need to query the sync history from the watcher process
        # For now, we can read directly from the sync history files
        from pathlib import Path

        from .sync_history import SyncHistory

        syftbox_dir = Path.home() / "SyftBox"
        sync_history = SyncHistory(syftbox_dir)

        return sync_history.get_history(file_path, limit=limit)
