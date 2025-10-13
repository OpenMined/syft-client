"""
Service management for watcher and receiver sync services
"""

import time
from typing import TYPE_CHECKING, Optional

import requests

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class SyncServiceManager:
    """Manages watcher and receiver services for automatic sync"""

    def __init__(self, client: "SyftClient"):
        self.client = client
        self._watcher = None
        self._receiver = None
        self._watcher_checked = False
        self._receiver_checked = False

    @property
    def watcher(self):
        """Get watcher server reference"""
        if not self._watcher_checked:
            self._check_and_link_watcher()
            self._watcher_checked = True
        return self._watcher

    @property
    def receiver(self):
        """Get receiver server reference"""
        if not self._receiver_checked:
            self._check_and_link_receiver()
            self._receiver_checked = True
        return self._receiver

    def _check_and_link_watcher(self):
        """Check if watcher is running and link it to the client"""
        try:
            import syft_serve as ss
        except ImportError:
            # syft-serve not installed, skip service management
            return

        # Create expected server name
        server_name = (
            f"watcher_sender_{self.client.email.replace('@', '_').replace('.', '_')}"
        )

        # Check if it exists
        existing_servers = list(ss.servers)
        for server in existing_servers:
            if server.name == server_name:
                # Found existing watcher
                self._watcher = server
                return

        # Not found, will be created on demand
        self._watcher = None

    def _check_and_link_receiver(self):
        """Check if receiver is running and link it to the client"""
        try:
            import syft_serve as ss
        except ImportError:
            # syft-serve not installed, skip service management
            return

        # Create expected server name
        server_name = (
            f"receiver_{self.client.email.replace('@', '_').replace('.', '_')}"
        )

        # Check if it exists
        existing_servers = list(ss.servers)
        for server in existing_servers:
            if server.name == server_name:
                # Found existing receiver
                self._receiver = server
                return

        # Not found, will be created on demand
        self._receiver = None

    def ensure_watcher_running(self, verbose: bool = False) -> bool:
        """Ensure watcher is running, start if not"""
        if self.watcher:
            # Already running and linked
            return True

        try:
            from ..sync.watcher.file_watcher import create_watcher_endpoint

            # Create and start watcher
            server = create_watcher_endpoint(self.client.email, verbose=verbose)
            self._watcher = server
            return True
        except Exception as e:
            if verbose:
                print(f"Warning: Could not start watcher: {e}")
            return False

    def ensure_receiver_running(self, verbose: bool = False) -> bool:
        """Ensure receiver is running, start if not"""
        if self.receiver:
            # Already running and linked
            return True

        try:
            from ..sync.receiver import create_receiver_endpoint

            # Create and start receiver
            server = create_receiver_endpoint(self.client.email, verbose=verbose)
            self._receiver = server
            return True
        except Exception as e:
            if verbose:
                print(f"Warning: Could not start receiver: {e}")
            return False

    def stop_watcher(self, verbose: bool = True) -> bool:
        """Stop the watcher service"""
        if self._watcher:
            try:
                self._watcher.terminate()
                self._watcher = None
                self._watcher_checked = False
                if verbose:
                    print(f"✓ Watcher stopped for {self.client.email}")
                return True
            except Exception as e:
                if verbose:
                    print(f"Error stopping watcher: {e}")
                return False
        return False

    def stop_receiver(self, verbose: bool = True) -> bool:
        """Stop the receiver service"""
        if self._receiver:
            try:
                self._receiver.terminate()
                self._receiver = None
                self._receiver_checked = False
                if verbose:
                    print(f"✓ Receiver stopped for {self.client.email}")
                return True
            except Exception as e:
                if verbose:
                    print(f"Error stopping receiver: {e}")
                return False
        return False

    def status(self, verbose: bool = True) -> dict:
        """Get status of both services"""
        watcher_status = "running" if self.watcher else "not running"
        receiver_status = "running" if self.receiver else "not running"

        status = {"watcher": watcher_status, "receiver": receiver_status}

        if verbose:
            print(f"📡 Sync services for {self.client.email}:")
            print(f"  - Watcher: {watcher_status}")
            print(f"  - Receiver: {receiver_status}")

        return status
