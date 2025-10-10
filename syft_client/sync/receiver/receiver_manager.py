"""
Client-side receiver management
"""

from typing import Any, Dict, List, Optional

import requests

from .receiver import create_receiver_endpoint, destroy_receiver_endpoint


class ReceiverManager:
    """Manages the inbox receiver for the client"""

    def __init__(self, client):
        self.client = client
        self._server = None
        self._server_name = (
            f"receiver_{client.email.replace('@', '_at_').replace('.', '_')}"
        )

    def start(
        self,
        check_interval: int = 2,
        process_immediately: bool = True,
        transports: Optional[List[str]] = None,
        auto_accept: bool = True,
        verbose: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Start the inbox receiver

        Args:
            check_interval: Seconds between inbox checks (default: 30)
            process_immediately: Process existing messages on start (default: True)
            transports: Specific transports to monitor (default: all)
            auto_accept: Auto-accept peer requests (default: True)
            verbose: Show status messages (default: True)
            **kwargs: Additional configuration options

        Returns:
            Status dictionary with receiver information
        """
        if self.is_running():
            return {
                "status": "already_running",
                "message": f"Receiver already active for {self.client.email}",
            }

        # Create and start the receiver endpoint
        self._server = create_receiver_endpoint(
            self.client.email,
            check_interval=check_interval,
            process_immediately=process_immediately,
            auto_accept=auto_accept,
            verbose=verbose,
        )

        return {
            "status": "started",
            "message": f"Receiver started for {self.client.email}",
            "check_interval": check_interval,
            "auto_accept": auto_accept,
        }

    def stop(self, verbose: bool = True) -> bool:
        """Stop the inbox receiver"""
        success = destroy_receiver_endpoint(self.client.email, verbose=verbose)
        if success:
            self._server = None
        return success

    def is_running(self) -> bool:
        """Check if receiver is running"""
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
        """Get receiver status"""
        if not self.is_running():
            return {"running": False, "message": "Receiver not running"}

        try:
            import syft_serve as ss

            for server in ss.servers:
                if server.name == self._server_name:
                    # Try to get stats from the receiver
                    stats = self.get_stats()

                    return {
                        "running": True,
                        "server_url": server.url,
                        "server_name": server.name,
                        "email": self.client.email,
                        "message": f"Receiver active for {self.client.email}",
                        **stats,  # Include stats if available
                    }
        except:
            pass

        return {"running": False, "message": "Unable to get receiver status"}

    def get_stats(self) -> Dict[str, Any]:
        """
        Get detailed statistics from the running receiver

        Returns:
            Dictionary with receiver statistics
        """
        try:
            import syft_serve as ss

            # Access the receiver's stats through the module
            # This is a bit hacky but works with syft-serve's architecture
            for server in ss.servers:
                if server.name == self._server_name:
                    # The stats are stored in the receiver module
                    # We can't directly access them via HTTP in current implementation
                    # Future enhancement: add a /stats endpoint
                    return {
                        "messages_processed": "unknown",
                        "last_check": "unknown",
                        "peers_monitored": (
                            len(list(self.client.peers))
                            if hasattr(self.client, "peers")
                            else 0
                        ),
                    }
        except:
            pass

        return {}

    def check_now(self) -> Dict[str, Any]:
        """
        Force an immediate inbox check (future enhancement)

        Returns:
            Result of the check
        """
        if not self.is_running():
            return {"status": "error", "message": "Receiver not running"}

        # This would require adding a /check endpoint to the receiver
        # For now, just return status
        return {
            "status": "not_implemented",
            "message": "Force check not yet implemented. Receiver checks automatically.",
        }

    def list_all(self) -> List[Dict[str, Any]]:
        """List all active receivers across all emails"""
        receivers = []
        try:
            import syft_serve as ss

            for server in ss.servers:
                if server.name.startswith("receiver_"):
                    # Extract email from server name
                    email_part = server.name.replace("receiver_", "")
                    email = email_part.replace("_at_", "@").replace("_", ".")

                    receivers.append(
                        {
                            "email": email,
                            "server_name": server.name,
                            "server_url": server.url,
                            "running": True,
                        }
                    )
        except ImportError:
            pass

        return receivers
