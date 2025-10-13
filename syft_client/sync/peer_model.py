"""
Peer model with transport capabilities tracking
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TransportEndpoint:
    """Information about a specific transport endpoint for a peer"""

    transport_name: str  # "gdrive_files", "gsheets", "gmail", etc.
    verified: bool = False  # Have we successfully used this?
    last_verified: Optional[datetime] = None
    endpoint_data: Dict[str, Any] = field(
        default_factory=dict
    )  # Transport-specific data
    restrictions: Optional[Dict[str, Any]] = None  # Size limits, rate limits, etc.

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        if self.last_verified:
            data["last_verified"] = self.last_verified.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransportEndpoint":
        """Create from dictionary"""
        if data.get("last_verified"):
            data["last_verified"] = datetime.fromisoformat(data["last_verified"])
        return cls(**data)


@dataclass
class TransportStats:
    """Historical performance data for a transport"""

    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0  # Sum of all latencies
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    failure_reasons: List[str] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency"""
        if self.success_count == 0:
            return 0.0
        return self.total_latency_ms / self.success_count

    def record_success(self, latency_ms: float):
        """Record a successful transport use"""
        self.success_count += 1
        self.total_latency_ms += latency_ms
        self.last_success = datetime.now()

    def record_failure(self, reason: str):
        """Record a failed transport use"""
        self.failure_count += 1
        self.last_failure = datetime.now()
        self.failure_reasons.append(f"{datetime.now().isoformat()}: {reason}")
        # Keep only last 10 failure reasons
        if len(self.failure_reasons) > 10:
            self.failure_reasons = self.failure_reasons[-10:]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        if self.last_success:
            data["last_success"] = self.last_success.isoformat()
        if self.last_failure:
            data["last_failure"] = self.last_failure.isoformat()
        # Add calculated average
        data["avg_latency_ms"] = self.avg_latency_ms
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TransportStats":
        """Create from dictionary"""
        # Remove calculated field if present
        data.pop("avg_latency_ms", None)
        if data.get("last_success"):
            data["last_success"] = datetime.fromisoformat(data["last_success"])
        if data.get("last_failure"):
            data["last_failure"] = datetime.fromisoformat(data["last_failure"])
        return cls(**data)


@dataclass
class Peer:
    """Represents a peer with their transport capabilities"""

    email: str
    platform: Optional[str] = None  # "google_org", "microsoft", etc.

    # Transport capabilities
    available_transports: Dict[str, TransportEndpoint] = field(default_factory=dict)
    capabilities_last_updated: Optional[datetime] = None

    # Relationship metadata
    added_date: datetime = field(default_factory=datetime.now)
    last_interaction: Optional[datetime] = None
    trust_level: str = "standard"  # "standard", "trusted", "restricted"

    # Performance history
    transport_stats: Dict[str, TransportStats] = field(default_factory=dict)

    def add_transport(
        self, transport_name: str, endpoint_data: Optional[Dict[str, Any]] = None
    ):
        """Add a transport capability to this peer"""
        self.available_transports[transport_name] = TransportEndpoint(
            transport_name=transport_name, endpoint_data=endpoint_data or {}
        )
        self.capabilities_last_updated = datetime.now()

    def verify_transport(self, transport_name: str):
        """Mark a transport as verified"""
        if transport_name in self.available_transports:
            self.available_transports[transport_name].verified = True
            self.available_transports[transport_name].last_verified = datetime.now()

    def get_verified_transports(self) -> List[str]:
        """Get list of verified transport names"""
        return [
            name
            for name, endpoint in self.available_transports.items()
            if endpoint.verified
        ]

    def record_transport_success(self, transport_name: str, latency_ms: float):
        """Record successful use of a transport"""
        if transport_name not in self.transport_stats:
            self.transport_stats[transport_name] = TransportStats()
        self.transport_stats[transport_name].record_success(latency_ms)
        self.last_interaction = datetime.now()
        self.verify_transport(transport_name)

    def record_transport_failure(self, transport_name: str, reason: str):
        """Record failed use of a transport"""
        if transport_name not in self.transport_stats:
            self.transport_stats[transport_name] = TransportStats()
        self.transport_stats[transport_name].record_failure(reason)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "email": self.email,
            "platform": self.platform,
            "available_transports": {
                name: endpoint.to_dict()
                for name, endpoint in self.available_transports.items()
            },
            "capabilities_last_updated": (
                self.capabilities_last_updated.isoformat()
                if self.capabilities_last_updated
                else None
            ),
            "added_date": self.added_date.isoformat(),
            "last_interaction": (
                self.last_interaction.isoformat() if self.last_interaction else None
            ),
            "trust_level": self.trust_level,
            "transport_stats": {
                name: stats.to_dict() for name, stats in self.transport_stats.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Peer":
        """Create from dictionary"""
        # Parse dates
        if data.get("capabilities_last_updated"):
            data["capabilities_last_updated"] = datetime.fromisoformat(
                data["capabilities_last_updated"]
            )
        if data.get("added_date"):
            data["added_date"] = datetime.fromisoformat(data["added_date"])
        if data.get("last_interaction"):
            data["last_interaction"] = datetime.fromisoformat(data["last_interaction"])

        # Parse transport endpoints
        if "available_transports" in data:
            data["available_transports"] = {
                name: TransportEndpoint.from_dict(endpoint)
                for name, endpoint in data["available_transports"].items()
            }

        # Parse transport stats
        if "transport_stats" in data:
            data["transport_stats"] = {
                name: TransportStats.from_dict(stats)
                for name, stats in data["transport_stats"].items()
            }

        return cls(**data)

    def save(self, directory: Path):
        """Save peer to disk"""
        directory.mkdir(parents=True, exist_ok=True)
        file_path = (
            directory / f"{self.email.replace('@', '_at_').replace('.', '_')}.json"
        )
        with open(file_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, file_path: Path) -> "Peer":
        """Load peer from disk"""
        with open(file_path, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)

    @property
    def platforms(self):
        """Access transport resources through platform hierarchy"""

        class PlatformAccess:
            def __init__(self, peer):
                self.peer = peer
                self._client = getattr(peer, "_client", None)
                if not self._client:
                    raise ValueError(
                        "Peer must be accessed through client.peers to use platforms"
                    )

            def __getattr__(self, platform_name):
                # Check if platform exists
                if platform_name not in self._client._platforms:
                    raise AttributeError(f"Platform '{platform_name}' not found")

                # Return transport accessor for this platform
                class TransportAccess:
                    def __init__(self, peer, platform, platform_name):
                        self.peer = peer
                        self.platform = platform
                        self.platform_name = platform_name

                    def __getattr__(self, transport_name):
                        # Check if transport exists
                        if not hasattr(self.platform, transport_name):
                            raise AttributeError(
                                f"Transport '{transport_name}' not found in {self.platform_name}"
                            )

                        transport = getattr(self.platform, transport_name)

                        # Create a transport stub that can be used to setup or get resources
                        class TransportStub:
                            def __init__(
                                self,
                                transport_obj,
                                peer_email,
                                platform_name,
                                transport_name,
                            ):
                                self._transport = transport_obj
                                self._peer_email = peer_email
                                self._platform_name = platform_name
                                self._transport_name = transport_name
                                self._resource = None

                                # Try to get resource if transport has the method
                                if hasattr(transport_obj, "get_peer_resource"):
                                    self._resource = transport_obj.get_peer_resource(
                                        peer_email
                                    )

                            def setup(self):
                                """Set up the communication channel with this peer on this transport"""
                                # For peer transport setup, we need to create the shared resources
                                # This means calling add_peer for this specific transport
                                if hasattr(self._transport, "add_peer"):
                                    try:
                                        # Add this peer on this specific transport
                                        result = self._transport.add_peer(
                                            self._peer_email, verbose=True
                                        )
                                        if result:
                                            # Update the peer's verified transports
                                            # Get the peer object through the client
                                            if hasattr(
                                                self._transport, "_platform_client"
                                            ):
                                                client = getattr(
                                                    self._transport._platform_client,
                                                    "_client",
                                                    None,
                                                )
                                                if client and hasattr(client, "sync"):
                                                    peer_obj = client.sync.peers_manager.get_peer(
                                                        self._peer_email
                                                    )
                                                    if peer_obj:
                                                        peer_obj.add_transport(
                                                            self._transport_name
                                                        )
                                                        peer_obj.verify_transport(
                                                            self._transport_name
                                                        )
                                                        client.sync.peers_manager._save_peer(
                                                            peer_obj
                                                        )
                                        return result
                                    except Exception as e:
                                        print(
                                            f"❌ Error setting up {self._transport_name} for {self._peer_email}: {e}"
                                        )
                                        return False
                                else:
                                    print(
                                        f"❌ Transport {self._transport_name} does not support peer setup"
                                    )
                                    return False

                            def is_setup(self):
                                """Check if transport is setup"""
                                if hasattr(self._transport, "is_setup"):
                                    return self._transport.is_setup()
                                return False

                            def __getattr__(self, name):
                                # If we have a resource, delegate to it
                                if self._resource and hasattr(self._resource, name):
                                    return getattr(self._resource, name)
                                # Otherwise delegate to the transport
                                return getattr(self._transport, name)

                            def __repr__(self):
                                if self._resource:
                                    return repr(self._resource)
                                else:
                                    setup_status = (
                                        "setup" if self.is_setup() else "not setup"
                                    )
                                    return f"<TransportStub {self._platform_name}.{self._transport_name} ({setup_status}) for {self._peer_email}>"

                        return TransportStub(
                            transport,
                            self.peer.email,
                            self.platform_name,
                            transport_name,
                        )

                    def __dir__(self):
                        """List available transports"""
                        transports = []

                        # Check each attribute to see if it's a transport
                        for attr in dir(self.platform):
                            if attr.startswith("_"):
                                continue

                            try:
                                obj = getattr(self.platform, attr)
                                # Check if it has transport-like methods
                                if hasattr(obj, "is_setup") and hasattr(obj, "setup"):
                                    transports.append(attr)
                            except:
                                pass

                        return sorted(transports)

                    def __repr__(self):
                        """Rich representation of transport resources"""
                        from io import StringIO

                        from rich.console import Console
                        from rich.panel import Panel
                        from rich.table import Table

                        string_buffer = StringIO()
                        console = Console(
                            file=string_buffer, force_terminal=True, width=80
                        )

                        table = Table(
                            show_header=False, show_edge=False, box=None, padding=0
                        )
                        table.add_column("", no_wrap=False)

                        # Add each transport with its resource status
                        # Only show transports that are in the peer's available_transports
                        for transport_name in sorted(self.__dir__()):
                            if (
                                hasattr(self.platform, transport_name)
                                and transport_name in self.peer.available_transports
                            ):
                                try:
                                    resource = getattr(self, transport_name)

                                    # Check if it's a PeerResource object
                                    if (
                                        resource
                                        and hasattr(resource, "__class__")
                                        and resource.__class__.__name__
                                        == "PeerResource"
                                    ):
                                        # Handle PeerResource objects
                                        if resource.available:
                                            status = f"[green]✓[/green] [cyan].{transport_name}[/cyan]"
                                            # Add resource type if not default
                                            if (
                                                hasattr(resource, "resource_type")
                                                and resource.resource_type != "folders"
                                            ):
                                                status += f" [dim]({resource.resource_type})[/dim]"
                                        else:
                                            status = f"[red]✗[/red] [dim].{transport_name}[/dim] [dim](not available)[/dim]"
                                    elif resource and isinstance(resource, dict):
                                        # Legacy dict handling
                                        if resource.get("available", True):
                                            # Extract display info from resource
                                            resource_type = resource.get(
                                                "type", "resource"
                                            )
                                            name = resource.get("name", "")
                                            url = resource.get("url", "")

                                            # Build status line
                                            status_parts = [
                                                f"[green]✓[/green] [cyan].{transport_name}[/cyan]"
                                            ]

                                            # Add resource details if available
                                            if name:
                                                # Truncate long names
                                                display_name = (
                                                    name[:30] + "..."
                                                    if len(name) > 30
                                                    else name
                                                )
                                                status_parts.append(
                                                    f"[dim]({resource_type}: {display_name})[/dim]"
                                                )
                                            elif resource_type != "resource":
                                                status_parts.append(
                                                    f"[dim]({resource_type})[/dim]"
                                                )

                                            status = " ".join(status_parts)

                                            # Add URL on next line if available
                                            if url:
                                                status += (
                                                    f"\n     [link={url}]→ Open[/link]"
                                                )
                                        else:
                                            status = f"[red]✗[/red] [dim].{transport_name}[/dim] [dim](not available)[/dim]"
                                    else:
                                        # Resource is None or not a dict/PeerResource
                                        status = f"[red]✗[/red] [dim].{transport_name}[/dim] [dim](no resource)[/dim]"
                                except Exception as e:
                                    status = f"[yellow]?[/yellow] [dim].{transport_name}[/dim] [dim](error: {str(e)[:20]}...)[/dim]"

                                table.add_row(status)

                        panel = Panel(
                            table,
                            title=f"{self.platform_name} Resources for {self.peer.email}",
                            expand=False,
                            width=80,
                        )

                        console.print(panel)
                        return string_buffer.getvalue().strip()

                return TransportAccess(
                    self.peer, self._client._platforms[platform_name], platform_name
                )

            def __dir__(self):
                """List available platforms"""
                return list(self._client._platforms.keys())

            def __repr__(self):
                """Rich representation of available platforms"""
                from io import StringIO

                from rich.console import Console
                from rich.panel import Panel
                from rich.table import Table

                string_buffer = StringIO()
                console = Console(file=string_buffer, force_terminal=True, width=80)

                table = Table(show_header=False, show_edge=False, box=None, padding=0)
                table.add_column("", no_wrap=False)

                # Show available platforms
                for platform_name in sorted(self._client._platforms.keys()):
                    # Count resources available
                    platform = self._client._platforms[platform_name]
                    resource_count = 0

                    # Check all transports dynamically
                    transport_access = getattr(self, platform_name)
                    for transport_name in transport_access.__dir__():
                        try:
                            resource = getattr(transport_access, transport_name)
                            if (
                                resource
                                and isinstance(resource, dict)
                                and resource.get("available", True)
                            ):
                                resource_count += 1
                        except:
                            pass

                    if resource_count > 0:
                        status = f"[green]✓[/green] [yellow].{platform_name}[/yellow] [dim]({resource_count} resources)[/dim]"
                    else:
                        status = f"[dim]✗ .{platform_name}[/dim]"

                    table.add_row(status)

                panel = Panel(
                    table,
                    title=f"Platforms for {self.peer.email}",
                    expand=False,
                    width=80,
                )

                console.print(panel)
                return string_buffer.getvalue().strip()

        return PlatformAccess(self)

    def __repr__(self) -> str:
        """Rich representation showing transport capabilities"""
        from io import StringIO

        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=80)

        # Create main table
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column("", no_wrap=False)

        # Add peer info
        main_table.add_row(f"[bold cyan]Email:[/bold cyan] {self.email}")
        if self.platform:
            main_table.add_row(f"[bold cyan]Platform:[/bold cyan] {self.platform}")

        # Add metadata
        main_table.add_row("")
        main_table.add_row(
            f"[dim]Added: {self.added_date.strftime('%Y-%m-%d %H:%M')}[/dim]"
        )
        if self.last_interaction:
            main_table.add_row(
                f"[dim]Last interaction: {self.last_interaction.strftime('%Y-%m-%d %H:%M')}[/dim]"
            )
        if self.capabilities_last_updated:
            main_table.add_row(
                f"[dim]Capabilities updated: {self.capabilities_last_updated.strftime('%Y-%m-%d %H:%M')}[/dim]"
            )

        # Add platforms section to hint at tab completion
        main_table.add_row("")
        main_table.add_row("[dim].platforms[/dim]")

        # Display platform and all its transports
        if (
            self.platform
            and hasattr(self, "_client")
            and self._client
            and self.platform in self._client._platforms
        ):
            main_table.add_row(f"  [bold yellow].{self.platform}[/bold yellow]")

            # Get all transports from the platform
            platform = self._client._platforms[self.platform]
            all_transports = []

            # Find all transport attributes on the platform
            for attr_name in dir(platform):
                if not attr_name.startswith("_"):
                    try:
                        obj = getattr(platform, attr_name)
                        # Check if it has transport-like methods
                        if hasattr(obj, "is_setup") and hasattr(obj, "setup"):
                            all_transports.append(attr_name)
                    except:
                        pass

            # Show each transport with appropriate status
            for transport_name in sorted(all_transports):
                if transport_name in self.available_transports:
                    endpoint = self.available_transports[transport_name]
                    # Status indicators
                    verified = (
                        "[green]✓[/green]" if endpoint.verified else "[red]✗[/red]"
                    )

                    # Performance info if available
                    perf_info = ""
                    if transport_name in self.transport_stats:
                        stats = self.transport_stats[transport_name]
                        if stats.success_count > 0:
                            success_rate = (
                                stats.success_count
                                / (stats.success_count + stats.failure_count)
                                * 100
                            )
                            perf_info = f" [dim]({success_rate:.0f}% success, {stats.avg_latency_ms:.0f}ms avg)[/dim]"

                    # Transport line with proper indentation
                    transport_line = (
                        f"    {verified} [cyan].{transport_name}[/cyan]{perf_info}"
                    )
                    main_table.add_row(transport_line)

                    # Show last verified time if available
                    if endpoint.verified and endpoint.last_verified:
                        time_ago = (
                            datetime.now() - endpoint.last_verified
                        ).total_seconds()
                        if time_ago < 3600:
                            time_str = f"{int(time_ago/60)} minutes ago"
                        elif time_ago < 86400:
                            time_str = f"{int(time_ago/3600)} hours ago"
                        else:
                            time_str = f"{int(time_ago/86400)} days ago"
                        main_table.add_row(f"       [dim]verified {time_str}[/dim]")
                else:
                    # Transport not in available_transports - show as inactive
                    transport_line = f"    [red]✗[/red] [dim].{transport_name}[/dim]"
                    main_table.add_row(transport_line)
        else:
            # Fallback to old behavior if platform not set properly
            platforms_with_transports = {}
            for transport_name, endpoint in self.available_transports.items():
                platform_key = self.platform or "unknown"
                if platform_key not in platforms_with_transports:
                    platforms_with_transports[platform_key] = []
                platforms_with_transports[platform_key].append(
                    (transport_name, endpoint)
                )

            # Display platforms and their transports
            for platform_key, transports in platforms_with_transports.items():
                main_table.add_row(f"  [bold yellow].{platform_key}[/bold yellow]")

                # Show transports under this platform
                for transport_name, endpoint in transports:
                    # Status indicators
                    verified = (
                        "[green]✓[/green]" if endpoint.verified else "[red]✗[/red]"
                    )

                    # Transport line with proper indentation
                    transport_line = f"    {verified} [cyan].{transport_name}[/cyan]"
                    main_table.add_row(transport_line)

                    # Show last verified time if available
                    if endpoint.verified and endpoint.last_verified:
                        time_ago = (
                            datetime.now() - endpoint.last_verified
                        ).total_seconds()
                        if time_ago < 3600:
                            time_str = f"{int(time_ago/60)} minutes ago"
                        elif time_ago < 86400:
                            time_str = f"{int(time_ago/3600)} hours ago"
                        else:
                            time_str = f"{int(time_ago/86400)} days ago"
                        main_table.add_row(f"       [dim]verified {time_str}[/dim]")

        if not self.available_transports:
            main_table.add_row("  [dim]No transports discovered yet[/dim]")

        # Create panel
        panel = Panel(
            main_table,
            title=f"Peer: {self.email.split('@')[0]}",
            expand=False,
            width=80,
            padding=(1, 2),
        )

        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()

        return output.strip()

    def check_inbox(
        self,
        download_dir: Optional[str] = None,
        verbose: bool = True,
        transport: Optional[str] = None,
    ) -> Dict[str, List[Dict]]:
        """
        Check all transport layers for incoming messages from this peer

        Args:
            download_dir: Optional directory to download messages to. If None, uses SyftBox directory
            verbose: Whether to print progress
            transport: Specific transport to check (e.g., "gdrive_files", "gsheets", "gmail").
                      If None, checks all verified transports.

        Returns:
            Dictionary mapping transport names to list of downloaded messages
        """
        if not hasattr(self, "_client") or not self._client:
            raise ValueError(
                "Peer must be accessed through client.peers to use check_inbox()"
            )

        results = {}
        total_messages = 0

        # Removed the initial message since receiver already logs it

        # Determine which transports to check
        if transport:
            # Check specific transport only
            if transport not in self.available_transports:
                print(f"❌ Transport '{transport}' is not available for {self.email}")
                print(
                    f"   Available transports: {list(self.available_transports.keys())}"
                )
                return {}
            if not self.available_transports[transport].verified:
                print(f"⚠️  Transport '{transport}' is not verified for {self.email}")
            transports_to_check = [transport]
        else:
            # Check all verified transports
            transports_to_check = self.get_verified_transports()

        # Check each transport
        for transport_name in transports_to_check:
            # Don't print transport checking messages for cleaner logs

            try:
                # Get the transport
                if self.platform not in self._client._platforms:
                    continue

                platform = self._client._platforms[self.platform]
                if not hasattr(platform, transport_name):
                    continue

                transport = getattr(platform, transport_name)

                # Check if transport has check_inbox method
                if hasattr(transport, "check_inbox"):
                    # Call transport-specific check_inbox
                    messages = transport.check_inbox(
                        sender_email=self.email,
                        download_dir=download_dir,
                        verbose=verbose,
                    )

                    if messages:
                        results[transport_name] = messages
                        total_messages += len(messages)
                        # Messages found - this will be logged in summary
                else:
                    if verbose:
                        print(f"   ⚠️  Transport doesn't support inbox checking")

            except Exception as e:
                if verbose:
                    print(f"   ❌ Error checking {transport_name}: {e}")

        if verbose:
            if total_messages > 0:
                print(
                    f"Found {total_messages} message{'s' if total_messages != 1 else ''}",
                    flush=True,
                )
            else:
                print(f"No messages", flush=True)

        return results


__all__ = ["Peer", "TransportEndpoint", "TransportStats"]
