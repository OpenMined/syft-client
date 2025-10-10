"""
Peer management for sync functionality
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from .discovery import PeerDiscovery
from .peer_model import Peer, TransportEndpoint
from .peer_request import PeerRequest

if TYPE_CHECKING:
    from ..syft_client import SyftClient


class PeerManager:
    """Manages peers for bidirectional communication"""

    def __init__(self, client: "SyftClient"):
        self.client = client
        self._peers_cache: Optional[Dict[str, Peer]] = None
        self._peers_cache_time: Optional[float] = None
        self._cache_ttl = 3600  # 1 hour cache
        self._peers_dir = None
        self._discovery = PeerDiscovery(client)

    @property
    def peers(self) -> List[str]:
        """
        List all peers (people you have set up outgoing channels to)

        Returns:
            List of email addresses you've added as peers
        """
        peers_dict = self.get_peers_dict()
        return list(peers_dict.keys())

    def get_peers_dict(self) -> Dict[str, Peer]:
        """
        Get all peers as a dictionary mapping emails to Peer objects

        Returns:
            Dict of email -> Peer objects
        """
        # Check if we have a valid platform with sync capability
        platform = self._get_sync_platform()
        if not platform:
            return {}

        # Check if cache is valid
        current_time = time.time()
        if (
            self._peers_cache is not None
            and self._peers_cache_time is not None
            and current_time - self._peers_cache_time < self._cache_ttl
        ):
            return self._peers_cache

        # Get peers from the platform
        peers_list = self._get_peers_from_platform(platform)

        # Load or create Peer objects
        peers_dict = {}
        for email in peers_list:
            peer = self._load_or_create_peer(email)

            # Re-verify which platforms actually have this peer
            platforms_with_peer = {}
            transports_with_peer = {}

            for platform_name, plat in self.client._platforms.items():
                # Check each transport on this platform
                for attr_name in dir(plat):
                    if not attr_name.startswith("_"):
                        transport = getattr(plat, attr_name, None)
                        if transport and hasattr(transport, "list_peers"):
                            try:
                                transport_peers = transport.list_peers()
                                if email in transport_peers:
                                    platforms_with_peer[platform_name] = plat
                                    if platform_name not in transports_with_peer:
                                        transports_with_peer[platform_name] = []
                                    transports_with_peer[platform_name].append(
                                        attr_name
                                    )
                            except:
                                pass

            # Update peer based on what we found
            if platforms_with_peer:
                # Determine correct platform
                # If peer already has a platform that's in the list, keep it
                # This prevents switching between google_personal and google_org unnecessarily
                correct_platform = None
                if peer.platform and peer.platform in platforms_with_peer:
                    correct_platform = peer.platform
                else:
                    # Otherwise, prefer the platform where we found more transports
                    max_transports = 0
                    for plat_name, transport_list in transports_with_peer.items():
                        if len(transport_list) > max_transports:
                            max_transports = len(transport_list)
                            correct_platform = plat_name

                    # If tied, prefer google_personal over google_org
                    if not correct_platform:
                        if "google_personal" in platforms_with_peer:
                            correct_platform = "google_personal"
                        elif "google_org" in platforms_with_peer:
                            correct_platform = "google_org"
                        else:
                            correct_platform = list(platforms_with_peer.keys())[0]

                # Update peer if platform changed or no transports
                if peer.platform != correct_platform or not peer.available_transports:
                    peer.platform = correct_platform
                    peer.available_transports.clear()

                    # Add and verify all transports found on the correct platform
                    for transport_name in transports_with_peer.get(
                        correct_platform, []
                    ):
                        peer.add_transport(transport_name)
                        peer.verify_transport(transport_name)

                    # For Google platforms, always add gmail if the platform has it
                    if correct_platform in ["google_personal", "google_org"]:
                        platform_obj = platforms_with_peer.get(correct_platform)
                        if platform_obj and hasattr(platform_obj, "gmail"):
                            gmail_transport = getattr(platform_obj, "gmail", None)
                            if (
                                gmail_transport
                                and hasattr(gmail_transport, "is_setup")
                                and gmail_transport.is_setup()
                            ):
                                if "gmail" not in peer.available_transports:
                                    peer.add_transport("gmail")
                                peer.verify_transport("gmail")

                    peer.capabilities_last_updated = datetime.now()
                    self._save_peer(peer)

                # Also verify any unverified transports
                elif peer.available_transports:
                    updated = False
                    for transport_name in transports_with_peer.get(peer.platform, []):
                        if (
                            transport_name in peer.available_transports
                            and not peer.available_transports[transport_name].verified
                        ):
                            peer.verify_transport(transport_name)
                            updated = True

                    # For Google platforms, ensure gmail is included and verified
                    if peer.platform in ["google_personal", "google_org"]:
                        platform_obj = platforms_with_peer.get(peer.platform)
                        if platform_obj and hasattr(platform_obj, "gmail"):
                            gmail_transport = getattr(platform_obj, "gmail", None)
                            if (
                                gmail_transport
                                and hasattr(gmail_transport, "is_setup")
                                and gmail_transport.is_setup()
                            ):
                                if "gmail" not in peer.available_transports:
                                    peer.add_transport("gmail")
                                    updated = True
                                if not peer.available_transports["gmail"].verified:
                                    peer.verify_transport("gmail")
                                    updated = True

                    if updated:
                        self._save_peer(peer)

            # If we didn't find the peer in any transports but it was loaded from disk,
            # keep it but note it needs re-discovery
            if not platforms_with_peer and not peer.available_transports:
                self._discover_peer_capabilities(peer, platform)

            peers_dict[email] = peer

        # Update cache
        self._peers_cache = peers_dict
        self._peers_cache_time = current_time

        return peers_dict

    def get_peer(self, email: str) -> Optional[Peer]:
        """
        Get a specific peer by email

        Args:
            email: Email address of the peer

        Returns:
            Peer object or None if not found
        """
        peers_dict = self.get_peers_dict()
        return peers_dict.get(email)

    def add_peer(self, email: str) -> bool:
        """
        Add a peer for bidirectional communication

        This will attempt to add the peer on ALL available transports
        to maximize connectivity options.

        Args:
            email: Email address of the peer to add

        Returns:
            True if peer was added on at least one transport
        """
        if not email or "@" not in email:
            print(f"❌ Invalid email address: {email}")
            return False

        # Check if trying to add self
        if email.lower() == self.client.email.lower():
            print("❌ Cannot add yourself as a peer")
            return False

        # Try to add peer on all available transports
        successful_transports = []
        failed_transports = []

        # Iterate through all platforms and their transports
        for platform_name, platform in self.client._platforms.items():
            # Get all transport attributes from the platform
            for attr_name in dir(platform):
                if not attr_name.startswith("_"):
                    transport = getattr(platform, attr_name, None)

                    # Check if this is a transport with add_peer method
                    if transport and hasattr(transport, "add_peer"):
                        try:
                            if self.client.verbose:
                                print(
                                    f"🔄 Adding {email} on {platform_name}.{attr_name}..."
                                )

                            # Call add_peer on the transport
                            result = transport.add_peer(email, verbose=False)

                            if result:
                                successful_transports.append(
                                    f"{platform_name}.{attr_name}"
                                )
                                if self.client.verbose:
                                    print(f"   ✅ Added on {platform_name}.{attr_name}")
                            else:
                                failed_transports.append(f"{platform_name}.{attr_name}")
                                if self.client.verbose:
                                    print(
                                        f"   ❌ Failed on {platform_name}.{attr_name}"
                                    )

                        except Exception as e:
                            failed_transports.append(f"{platform_name}.{attr_name}")
                            if self.client.verbose:
                                print(
                                    f"   ❌ Error on {platform_name}.{attr_name}: {e}"
                                )

        # Summary
        if successful_transports:
            if self.client.verbose:
                print(
                    f"\n✅ Peer {email} added successfully on {len(successful_transports)} transport(s)"
                )
                for transport in successful_transports:
                    print(f"   • {transport}")

            # Invalidate cache and force rediscovery
            self._invalidate_peers_cache()

            # Create or update peer object with discovered transports
            peer = self._load_or_create_peer(email)

            # Set platform based on successful transports
            platforms_used = set()
            for transport_path in successful_transports:
                platform_name, transport_name = transport_path.split(".")
                platforms_used.add(platform_name)
                peer.add_transport(transport_name)
                peer.verify_transport(transport_name)

            # Set the platform if we have a clear winner
            if len(platforms_used) == 1:
                peer.platform = list(platforms_used)[0]
            elif "google_personal" in platforms_used:
                peer.platform = "google_personal"  # Prefer personal
            elif "google_org" in platforms_used:
                peer.platform = "google_org"

            self._save_peer(peer)

            return True
        else:
            print(f"❌ Failed to add peer {email} on any transport")
            return False

    def remove_peer(self, email: str) -> bool:
        """
        Remove a peer from all transports

        Args:
            email: Email address of the peer to remove

        Returns:
            True if peer was removed from at least one transport
        """
        # Check if peer exists
        if email not in self.peers:
            print(f"❌ {email} is not in your peers list")
            return False

        # Try to remove peer from all transports
        successful_removals = []
        failed_removals = []

        # Iterate through all platforms and their transports
        for platform_name, platform in self.client._platforms.items():
            # Get all transport attributes from the platform
            for attr_name in dir(platform):
                if not attr_name.startswith("_"):
                    transport = getattr(platform, attr_name, None)

                    # Check if this is a transport with remove_peer method
                    if transport and hasattr(transport, "remove_peer"):
                        try:
                            if self.client.verbose:
                                print(
                                    f"🔄 Removing {email} from {platform_name}.{attr_name}..."
                                )

                            # Call remove_peer on the transport
                            result = transport.remove_peer(email, verbose=False)

                            if result:
                                successful_removals.append(
                                    f"{platform_name}.{attr_name}"
                                )
                                if self.client.verbose:
                                    print(
                                        f"   ✅ Removed from {platform_name}.{attr_name}"
                                    )
                            else:
                                failed_removals.append(f"{platform_name}.{attr_name}")
                                if self.client.verbose:
                                    print(
                                        f"   ⚠️  Not found on {platform_name}.{attr_name}"
                                    )

                        except Exception as e:
                            failed_removals.append(f"{platform_name}.{attr_name}")
                            if self.client.verbose:
                                print(
                                    f"   ❌ Error on {platform_name}.{attr_name}: {e}"
                                )

        # Summary and cleanup
        if successful_removals:
            if self.client.verbose:
                print(
                    f"\n✅ Peer {email} removed from {len(successful_removals)} transport(s)"
                )

            # Remove peer file
            try:
                peers_dir = self._get_peers_directory()
                file_name = f"{email.replace('@', '_at_').replace('.', '_')}.json"
                file_path = peers_dir / file_name
                if file_path.exists():
                    file_path.unlink()
            except:
                pass

            # Invalidate cache
            self._invalidate_peers_cache()
            return True
        else:
            print(f"⚠️  {email} was not found on any transport")
            return False

    def _invalidate_peers_cache(self):
        """Invalidate the peers cache to force a refresh on next access"""
        self._peers_cache = None
        self._peers_cache_time = None

    def delete_peer(self, email: str) -> bool:
        """
        Delete a peer completely, removing all transport objects and local caches

        This performs a complete deletion:
        1. Removes peer from all transports (unshares resources)
        2. Deletes all Google Drive folders (outbox/inbox and archive)
        3. Deletes all Google Sheets
        4. Removes Gmail labels
        5. Clears local peer cache files
        6. Clears discovery cache

        Args:
            email: Email address of the peer to delete

        Returns:
            True if peer was successfully deleted
        """
        if not email or "@" not in email:
            print(f"❌ Invalid email address: {email}")
            return False

        # Check if peer exists
        if email not in self.peers:
            print(f"❌ {email} is not in your peers list")
            return False

        print(f"🗑️  Deleting peer {email} completely...")

        # First, remove the peer using the standard remove_peer method
        # This will revoke access permissions
        print(f"📤 Removing {email} from all transports...")
        self.remove_peer(email)

        deletion_results = {
            "gdrive_folders": [],
            "gsheets": [],
            "gmail_labels": [],
            "local_cache": False,
            "discovery_cache": False,
        }

        # Delete from all transports
        for platform_name, platform in self.client._platforms.items():
            # Get all transport attributes from the platform
            for attr_name in dir(platform):
                if not attr_name.startswith("_"):
                    transport = getattr(platform, attr_name, None)

                    # Handle Google Drive folders
                    if (
                        transport
                        and attr_name == "gdrive_files"
                        and hasattr(transport, "drive_service")
                    ):
                        try:
                            if self.client.verbose:
                                print(
                                    f"\n📁 Deleting Google Drive folders on {platform_name}..."
                                )

                            # Get the email used in folder names (might be different from peer email)
                            my_email = self.client.email

                            # Delete all possible folder patterns with @ and with underscores
                            folder_patterns = [
                                # Patterns with @ in emails
                                f"syft_{my_email}_to_{email}_outbox_inbox",
                                f"syft_{email}_to_{my_email}_outbox_inbox",
                                f"syft_{email}_to_{my_email}_archive",
                                f"syft_{my_email}_to_{email}_archive",
                                f"syft_{my_email}_to_{email}_pending",
                                # Patterns with underscores replacing @ and .
                                f"syft_{my_email.replace('@', '_at_').replace('.', '_')}_to_{email.replace('@', '_at_').replace('.', '_')}_outbox_inbox",
                                f"syft_{email.replace('@', '_at_').replace('.', '_')}_to_{my_email.replace('@', '_at_').replace('.', '_')}_outbox_inbox",
                                f"syft_{email.replace('@', '_at_').replace('.', '_')}_to_{my_email.replace('@', '_at_').replace('.', '_')}_archive",
                                f"syft_{my_email.replace('@', '_at_').replace('.', '_')}_to_{email.replace('@', '_at_').replace('.', '_')}_archive",
                                f"syft_{my_email.replace('@', '_at_').replace('.', '_')}_to_{email.replace('@', '_at_').replace('.', '_')}_pending",
                            ]

                            for folder_name in folder_patterns:
                                results = self._delete_gdrive_folder(
                                    transport, folder_name
                                )
                                if results:
                                    deletion_results["gdrive_folders"].extend(results)

                        except Exception as e:
                            if self.client.verbose:
                                print(f"   ❌ Error deleting Drive folders: {e}")

                    # Handle Google Sheets
                    elif (
                        transport
                        and attr_name == "gsheets"
                        and hasattr(transport, "drive_service")
                    ):
                        try:
                            if self.client.verbose:
                                print(
                                    f"\n📊 Deleting Google Sheets on {platform_name}..."
                                )

                            my_email = self.client.email

                            # Delete outgoing messages sheet (where I send to them)
                            sheet_name = f"syft_{my_email}_to_{email}_messages"
                            results = self._delete_gsheet(transport, sheet_name)
                            if results:
                                deletion_results["gsheets"].extend(results)

                            # Also try with underscores in email addresses
                            sheet_name_underscore = f"syft_{my_email.replace('@', '_at_').replace('.', '_')}_to_{email.replace('@', '_at_').replace('.', '_')}_messages"
                            results = self._delete_gsheet(
                                transport, sheet_name_underscore
                            )
                            if results:
                                deletion_results["gsheets"].extend(results)

                            # Delete incoming messages sheet (where they send to me)
                            incoming_sheet_name = f"syft_{email}_to_{my_email}_messages"
                            results = self._delete_gsheet(
                                transport, incoming_sheet_name
                            )
                            if results:
                                deletion_results["gsheets"].extend(results)

                            # Also try with underscores in email addresses
                            incoming_sheet_name_underscore = f"syft_{email.replace('@', '_at_').replace('.', '_')}_to_{my_email.replace('@', '_at_').replace('.', '_')}_messages"
                            results = self._delete_gsheet(
                                transport, incoming_sheet_name_underscore
                            )
                            if results:
                                deletion_results["gsheets"].extend(results)

                        except Exception as e:
                            if self.client.verbose:
                                print(f"   ❌ Error deleting Sheets: {e}")

                    # Handle Gmail labels
                    elif (
                        transport
                        and attr_name == "gmail"
                        and hasattr(transport, "gmail_service")
                    ):
                        try:
                            if self.client.verbose:
                                print(
                                    f"\n✉️  Removing Gmail labels on {platform_name}..."
                                )

                            # Remove labels
                            labels = [f"SyftBox/From/{email}", f"SyftBox/To/{email}"]

                            for label in labels:
                                if self._delete_gmail_label(transport, label):
                                    deletion_results["gmail_labels"].append(label)

                        except Exception as e:
                            if self.client.verbose:
                                print(f"   ❌ Error removing Gmail labels: {e}")

        # Delete local peer cache file
        try:
            peers_dir = self._get_peers_directory()
            file_name = f"{email.replace('@', '_at_').replace('.', '_')}.json"
            file_path = peers_dir / file_name
            if file_path.exists():
                file_path.unlink()
                deletion_results["local_cache"] = True
                if self.client.verbose:
                    print(f"\n🗄️  Deleted local peer cache file")
        except Exception as e:
            if self.client.verbose:
                print(f"\n❌ Error deleting peer cache: {e}")

        # Delete discovery cache
        try:
            discovery_cache = (
                self._discovery._get_discovery_cache_dir()
                / f"{email.replace('@', '_at_').replace('.', '_')}_discovery.json"
            )
            if discovery_cache.exists():
                discovery_cache.unlink()
                deletion_results["discovery_cache"] = True
                if self.client.verbose:
                    print(f"🔍 Deleted discovery cache")
        except Exception as e:
            if self.client.verbose:
                print(f"❌ Error deleting discovery cache: {e}")

        # Invalidate memory cache
        self._invalidate_peers_cache()

        # Summary
        total_deleted = (
            len(deletion_results["gdrive_folders"])
            + len(deletion_results["gsheets"])
            + len(deletion_results["gmail_labels"])
            + (1 if deletion_results["local_cache"] else 0)
            + (1 if deletion_results["discovery_cache"] else 0)
        )

        if total_deleted > 0:
            print(f"\n✅ Successfully deleted peer {email}")
            if self.client.verbose:
                print(
                    f"   • Google Drive folders: {len(deletion_results['gdrive_folders'])}"
                )
                print(f"   • Google Sheets: {len(deletion_results['gsheets'])}")
                print(f"   • Gmail labels: {len(deletion_results['gmail_labels'])}")
                print(
                    f"   • Local cache: {'✓' if deletion_results['local_cache'] else '✗'}"
                )
                print(
                    f"   • Discovery cache: {'✓' if deletion_results['discovery_cache'] else '✗'}"
                )
            return True
        else:
            print(f"⚠️  No resources found to delete for {email}")
            return False

    def _delete_gdrive_folder(self, transport, folder_name: str) -> List[str]:
        """Delete a Google Drive folder by name"""
        deleted = []
        try:
            # Search for the folder
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = (
                transport.drive_service.files()
                .list(q=query, fields="files(id, name)")
                .execute()
            )

            folders = results.get("files", [])
            for folder in folders:
                try:
                    # Move to trash (can be recovered)
                    transport.drive_service.files().update(
                        fileId=folder["id"], body={"trashed": True}
                    ).execute()
                    deleted.append(folder["name"])
                    if self.client.verbose:
                        print(f"   ✓ Deleted folder: {folder['name']}")
                except Exception as e:
                    if self.client.verbose:
                        print(f"   ⚠️  Could not delete {folder['name']}: {e}")

        except Exception as e:
            if self.client.verbose:
                print(f"   ❌ Error searching for folders: {e}")

        return deleted

    def _delete_gsheet(self, transport, sheet_name: str) -> List[str]:
        """Delete a Google Sheet by name"""
        deleted = []
        try:
            # Search for the sheet
            query = f"name='{sheet_name}' and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
            results = (
                transport.drive_service.files()
                .list(q=query, fields="files(id, name)")
                .execute()
            )

            sheets = results.get("files", [])
            for sheet in sheets:
                try:
                    # Move to trash
                    transport.drive_service.files().update(
                        fileId=sheet["id"], body={"trashed": True}
                    ).execute()
                    deleted.append(sheet["name"])
                    if self.client.verbose:
                        print(f"   ✓ Deleted sheet: {sheet['name']}")
                except Exception as e:
                    if self.client.verbose:
                        print(f"   ⚠️  Could not delete {sheet['name']}: {e}")

        except Exception as e:
            if self.client.verbose:
                print(f"   ❌ Error searching for sheets: {e}")

        return deleted

    def _delete_gmail_label(self, transport, label_name: str) -> bool:
        """Delete a Gmail label"""
        try:
            # Get all labels
            results = (
                transport.gmail_service.users().labels().list(userId="me").execute()
            )
            labels = results.get("labels", [])

            # Find the label
            for label in labels:
                if label["name"] == label_name:
                    try:
                        # Delete the label
                        transport.gmail_service.users().labels().delete(
                            userId="me", id=label["id"]
                        ).execute()
                        if self.client.verbose:
                            print(f"   ✓ Deleted label: {label_name}")
                        return True
                    except Exception as e:
                        if self.client.verbose:
                            print(f"   ⚠️  Could not delete {label_name}: {e}")
                        return False

        except Exception as e:
            if self.client.verbose:
                print(f"   ❌ Error with Gmail labels: {e}")

        return False

    def clear_all_caches(self, verbose: bool = True) -> None:
        """
        Clear all peer caches from disk and memory, forcing re-detection from online sources

        This will:
        1. Clear in-memory peers cache
        2. Delete all saved peer JSON files
        3. Delete all discovery cache files
        4. Force fresh discovery on next access

        Args:
            verbose: If True, print detailed progress. If False, operate silently.
        """
        if verbose:
            print("🗑️  Clearing all peer caches...")

        # Clear in-memory cache
        self._invalidate_peers_cache()

        files_cleared = 0

        # Clear peer JSON files
        try:
            peers_dir = self._get_peers_directory()
            if peers_dir.exists():
                for file_path in peers_dir.glob("*.json"):
                    try:
                        file_path.unlink()
                        files_cleared += 1
                        if verbose:
                            print(f"   ✓ Deleted peer file: {file_path.name}")
                    except Exception as e:
                        if verbose:
                            print(f"   ⚠️  Could not delete {file_path.name}: {e}")
        except Exception as e:
            if verbose:
                print(f"   ⚠️  Error clearing peer files: {e}")

        # Clear discovery cache
        try:
            discovery_cache_dir = self._discovery._get_discovery_cache_dir()
            if discovery_cache_dir.exists():
                for file_path in discovery_cache_dir.glob("*_discovery.json"):
                    try:
                        file_path.unlink()
                        files_cleared += 1
                        if verbose:
                            print(f"   ✓ Deleted discovery cache: {file_path.name}")
                    except Exception as e:
                        if verbose:
                            print(f"   ⚠️  Could not delete {file_path.name}: {e}")
        except Exception as e:
            if verbose:
                print(f"   ⚠️  Error clearing discovery cache: {e}")

        if verbose and files_cleared > 0:
            print(
                "✅ All peer caches cleared. Next access will fetch fresh data from online sources."
            )
        elif verbose:
            print("ℹ️  No peer caches found to clear.")

    def _get_sync_platform(self):
        """Get a platform that supports sync functionality"""
        # Look for platforms with sync capabilities
        # Priority order: google_org, google_personal
        for platform_name in ["google_org", "google_personal"]:
            if platform_name in self.client._platforms:
                platform = self.client._platforms[platform_name]
                # Check if it has the required transport
                if hasattr(platform, "gdrive_files"):
                    return platform

        return None

    def _get_peers_from_platform(self, platform) -> List[str]:
        """Get peers list from all transports across all platforms"""
        all_peers = set()  # Use set to avoid duplicates

        # Iterate through all platforms
        for platform_name, platform in self.client._platforms.items():
            # Get all transport attributes from the platform
            for attr_name in dir(platform):
                if not attr_name.startswith("_"):
                    transport = getattr(platform, attr_name, None)

                    # Check if this is a transport with list_peers method
                    if transport and hasattr(transport, "list_peers"):
                        try:
                            peers = transport.list_peers()
                            all_peers.update(peers)
                        except:
                            pass

        return list(all_peers)

    def _get_peers_directory(self) -> Path:
        """Get the directory where peer data is stored"""
        if not self._peers_dir:
            if hasattr(self.client, "local_syftbox_dir"):
                self._peers_dir = self.client.local_syftbox_dir / ".syft" / "peers"
            else:
                # Fallback to home directory
                self._peers_dir = Path.home() / ".syft" / "peers"
            self._peers_dir.mkdir(parents=True, exist_ok=True)
        return self._peers_dir

    def _load_or_create_peer(self, email: str) -> Peer:
        """Load peer from disk or create new one"""
        peers_dir = self._get_peers_directory()
        file_name = f"{email.replace('@', '_at_').replace('.', '_')}.json"
        file_path = peers_dir / file_name

        if file_path.exists():
            try:
                peer = Peer.load(file_path)

                # If peer has no platform but has transports, determine platform
                if not peer.platform and peer.available_transports:
                    # Determine platform from available transports
                    platforms_found = set()

                    # Check which platforms have these transports
                    for platform_name, platform in self.client._platforms.items():
                        platform_has_transports = True
                        for transport_name in peer.available_transports:
                            if not hasattr(platform, transport_name):
                                platform_has_transports = False
                                break
                        if platform_has_transports:
                            platforms_found.add(platform_name)

                    # Set platform if we can determine it
                    if len(platforms_found) == 1:
                        peer.platform = list(platforms_found)[0]
                    elif "google_org" in platforms_found and email.endswith(
                        "@openmined.org"
                    ):
                        # For OpenMined emails, prefer google_org
                        peer.platform = "google_org"
                    elif "google_personal" in platforms_found:
                        peer.platform = "google_personal"
                    elif "google_org" in platforms_found:
                        peer.platform = "google_org"

                    # Save the updated peer
                    if peer.platform:
                        self._save_peer(peer)

                return peer
            except Exception as e:
                if self.client.verbose:
                    print(f"⚠️  Could not load peer data for {email}: {e}")

        # Create new peer
        peer = Peer(email=email)

        # Check discovery cache
        cached_discovery = self._discovery.load_discovery_cache(email)
        if cached_discovery:
            # Apply cached discovery data
            peer.platform = cached_discovery.get("platform")
            for transport in cached_discovery.get("transports", []):
                peer.add_transport(transport)
            for transport in cached_discovery.get("verified_transports", []):
                peer.verify_transport(transport)
            if self.client.verbose:
                print(f"📋 Loaded cached capabilities for {email}")

        return peer

    def _save_peer(self, peer: Peer):
        """Save peer to disk"""
        peers_dir = self._get_peers_directory()
        try:
            peer.save(peers_dir)
        except Exception as e:
            if self.client.verbose:
                print(f"⚠️  Could not save peer data for {peer.email}: {e}")

    def _discover_peer_capabilities(self, peer: Peer, platform):
        """Discover what transports a peer has available"""
        # Use the discovery system
        if self._discovery.discover_capabilities(peer):
            # Save discovered capabilities
            self._save_peer(peer)
            self._discovery.save_discovery_cache(peer)

    def check_all_peer_requests(
        self, verbose: bool = True
    ) -> Dict[str, List[PeerRequest]]:
        """
        Check all transports for incoming peer requests

        Args:
            verbose: Whether to print summary

        Returns:
            Dictionary mapping platform.transport to list of PeerRequest objects
        """
        all_requests = {}
        total_count = 0

        # Check each platform and transport
        for platform_name, platform in self.client._platforms.items():
            # Get all transport attributes from the platform
            for attr_name in dir(platform):
                if not attr_name.startswith("_"):
                    transport = getattr(platform, attr_name, None)

                    # Check if this transport has check_peer_requests method
                    if transport and hasattr(transport, "check_peer_requests"):
                        try:
                            # Get pending requests from this transport
                            request_emails = transport.check_peer_requests()

                            if request_emails:
                                transport_key = f"{platform_name}.{attr_name}"
                                requests = []

                                for email in request_emails:
                                    request = PeerRequest(
                                        email=email,
                                        platform=platform_name,
                                        transport=attr_name,
                                    )
                                    requests.append(request)

                                all_requests[transport_key] = requests
                                total_count += len(requests)

                        except Exception as e:
                            if self.client.verbose:
                                print(
                                    f"Error checking {platform_name}.{attr_name}: {e}"
                                )

        # Print summary if verbose
        if verbose and total_count > 0:
            print(
                f"\n📬 You have {total_count} pending peer request{'s' if total_count != 1 else ''}:"
            )

            # Group by email to show unique peers
            unique_peers = {}
            for transport_key, requests in all_requests.items():
                for request in requests:
                    if request.email not in unique_peers:
                        unique_peers[request.email] = []
                    unique_peers[request.email].append(
                        f"{request.platform}.{request.transport}"
                    )

            # Show each unique peer
            for email, transports in unique_peers.items():
                transports_str = ", ".join(transports)
                print(f"   • {email} (via {transports_str})")

            print(
                "\nTo accept a peer request, use: client.add_peer('email@example.com')"
            )

        return all_requests


__all__ = ["PeerManager"]
