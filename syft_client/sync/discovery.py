"""
Transport capability discovery for contacts
"""

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .peer_model import Peer, TransportEndpoint

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class PeerDiscovery:
    """Discovers transport capabilities for contacts"""

    def __init__(self, client: "SyftClient"):
        self.client = client
        self._discovery_cache_dir = None

    def discover_capabilities(self, peer: Peer) -> bool:
        """
        Discover transport capabilities for a peer

        This method will try various strategies to determine what
        transports a peer has available.

        Args:
            peer: Peer object to discover capabilities for

        Returns:
            True if any capabilities were discovered
        """
        discovered_any = False

        # Strategy 1: Domain-based discovery
        if self._discover_by_domain(peer):
            discovered_any = True

        # Strategy 2: Shared directory discovery (Google Drive)
        if self._discover_by_shared_directory(peer):
            discovered_any = True

        # Strategy 3: Probe-based discovery
        if self._discover_by_probing(peer):
            discovered_any = True

        # Update discovery timestamp
        if discovered_any:
            peer.capabilities_last_updated = datetime.now()

        return discovered_any

    def _discover_by_domain(self, peer: Peer) -> bool:
        """
        Discover capabilities based on email domain

        This is a simple heuristic that assumes certain domains
        support certain transports.
        """
        email_domain = peer.email.split("@")[-1].lower()
        discovered = False

        # Google domains
        if any(
            domain in email_domain
            for domain in ["google.com", "gmail.com", "googlemail.com"]
        ):
            peer.platform = "google_personal"  # More specific
            # All Google users have these capabilities
            for transport in ["gdrive_files", "gsheets", "gmail"]:
                if transport not in peer.available_transports:
                    peer.add_transport(transport)
                    discovered = True

        # Microsoft domains
        elif any(
            domain in email_domain
            for domain in ["microsoft.com", "outlook.com", "hotmail.com", "live.com"]
        ):
            peer.platform = "microsoft"
            # Microsoft users likely have OneDrive
            if "onedrive" not in peer.available_transports:
                peer.add_transport("onedrive")
                discovered = True

        # Corporate/educational domains - check if G Suite
        elif self._is_gsuite_domain(email_domain):
            peer.platform = "google_org"  # Google Workspace/organizational
            for transport in ["gdrive_files", "gsheets", "gmail"]:
                if transport not in peer.available_transports:
                    peer.add_transport(transport)
                    discovered = True

        # For any domain, if we found Google transports, set appropriate platform
        elif (
            "gdrive_files" in peer.available_transports
            or "gsheets" in peer.available_transports
        ):
            # If we have Google transports, determine if org or personal
            # For now, assume org for non-gmail domains
            if "gmail.com" not in email_domain:
                peer.platform = "google_org"
            else:
                peer.platform = "google_personal"
            discovered = True

        return discovered

    def _is_gsuite_domain(self, domain: str) -> bool:
        """
        Check if a domain uses Google Workspace (G Suite)

        This would ideally check MX records or use Google's API,
        but for now we'll use a simple heuristic.
        """
        # Common educational/corporate TLDs that often use G Suite
        gsuite_tlds = [".edu", ".ac.uk", ".edu.au", ".edu.cn"]

        # Known domains that use Google Workspace
        known_gsuite_domains = ["openmined.org"]

        return (
            any(domain.endswith(tld) for tld in gsuite_tlds)
            or domain in known_gsuite_domains
        )

    def _discover_by_shared_directory(self, peer: Peer) -> bool:
        """
        Discover capabilities by checking shared directories

        For Google Drive, we can check if the peer has access
        to shared folders, which indicates they have Google Drive.
        """
        discovered = False

        # Check if we have Google Drive access
        platform = self._get_google_platform()
        if not platform or not hasattr(platform, "gdrive_files"):
            return False

        try:
            gdrive = platform.gdrive_files

            # Look for shared folders with this contact
            # This is a simplified check - real implementation would
            # query the Drive API for shared folders
            if hasattr(gdrive, "check_user_has_drive"):
                if gdrive.check_user_has_drive(peer.email):
                    if "gdrive_files" not in peer.available_transports:
                        peer.add_transport("gdrive_files")
                        peer.verify_transport("gdrive_files")
                        discovered = True

                    # If they have Drive, they likely have Sheets too
                    if "gsheets" not in peer.available_transports:
                        peer.add_transport("gsheets")
                        discovered = True
        except:
            pass

        return discovered

    def _discover_by_probing(self, peer: Peer) -> bool:
        """
        Discover capabilities by sending probe messages

        This method would send small test messages through different
        transports to see which ones work. For privacy and efficiency,
        this should be done sparingly.
        """
        # For now, this is a placeholder
        # Real implementation would:
        # 1. Send tiny probe messages through each transport
        # 2. Wait for delivery confirmation
        # 3. Mark transports as verified if successful
        return False

    def _get_google_platform(self):
        """Get a Google platform if available"""
        for platform_name in ["google_org", "google_personal"]:
            if platform_name in self.client._platforms:
                return self.client._platforms[platform_name]
        return None

    def save_discovery_cache(self, peer: Peer):
        """Save discovered capabilities to cache"""
        cache_dir = self._get_discovery_cache_dir()
        cache_file = cache_dir / f"{peer.email.replace('@', '_at_')}_discovery.json"

        try:
            discovery_data = {
                "email": peer.email,
                "platform": peer.platform,
                "transports": list(peer.available_transports.keys()),
                "verified_transports": peer.get_verified_transports(),
                "last_updated": (
                    peer.capabilities_last_updated.isoformat()
                    if peer.capabilities_last_updated
                    else None
                ),
            }

            with open(cache_file, "w") as f:
                json.dump(discovery_data, f, indent=2)
        except Exception as e:
            if self.client.verbose:
                print(f"⚠️  Could not save discovery cache for {peer.email}: {e}")

    def load_discovery_cache(self, email: str) -> Optional[Dict[str, Any]]:
        """Load discovered capabilities from cache"""
        cache_dir = self._get_discovery_cache_dir()
        cache_file = cache_dir / f"{email.replace('@', '_at_')}_discovery.json"

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    return json.load(f)
            except:
                pass

        return None

    def _get_discovery_cache_dir(self) -> Path:
        """Get directory for discovery cache"""
        if not self._discovery_cache_dir:
            if hasattr(self.client, "local_syftbox_dir"):
                self._discovery_cache_dir = (
                    self.client.local_syftbox_dir / ".syft" / "discovery"
                )
            else:
                self._discovery_cache_dir = Path.home() / ".syft" / "discovery"
            self._discovery_cache_dir.mkdir(parents=True, exist_ok=True)
        return self._discovery_cache_dir


class TransportProbe:
    """
    Sends probe messages to test transport availability

    This is a placeholder for future implementation that would
    send small test messages to verify transport capabilities.
    """

    def __init__(self, client: "SyftClient"):
        self.client = client

    def probe_transport(self, peer_email: str, transport_name: str) -> bool:
        """
        Send a probe message to test if a transport works

        Args:
            peer_email: Email of the peer to probe
            transport_name: Name of the transport to test

        Returns:
            True if the probe was successful
        """
        # Placeholder for future implementation
        # Would send a small test message and wait for confirmation
        return False


__all__ = ["PeerDiscovery", "TransportProbe"]
