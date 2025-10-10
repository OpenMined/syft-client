class PeersProperty:
    def __init__(self, sync_manager, client):
        self._sync = sync_manager
        self._client = client  # Store reference to the client

    def __getitem__(self, key):
        if isinstance(key, int):
            # List-style access: peers[0]
            peer_list = self._sync.peers
            if 0 <= key < len(peer_list):
                email = peer_list[key]
                peer = self._sync.peers_manager.get_peer(email)
                if peer:
                    # Inject client reference
                    peer._client = self._client
                return peer
            else:
                raise IndexError(f"Peer index {key} out of range")
        elif isinstance(key, str):
            # Dict-style access: peers['email@example.com']
            peer = self._sync.peers_manager.get_peer(key)
            if peer is None:
                raise KeyError(f"Peer '{key}' not found")
            # Inject client reference
            peer._client = self._client
            return peer
        else:
            raise TypeError(f"Invalid key type: {type(key)}")

    def __len__(self):
        return len(self._sync.peers)

    def __iter__(self):
        # Allow iteration over peer emails
        return iter(self._sync.peers)

    def list(self):
        """Get list of peer emails"""
        return self._sync.peers

    def all(self):
        """Get all peer objects"""
        return [self._sync.peers_manager.get_peer(email) for email in self._sync.peers]

    def clear_caches(self):
        """Clear all peer caches and force re-detection from online sources"""
        return self._sync.peers_manager.clear_all_caches()

    @property
    def requests(self):
        """Access peer requests"""

        class PeerRequestsProperty:
            def __init__(self, sync_manager):
                self._sync = sync_manager
                self._requests_cache = None

            def _get_all_requests(self):
                """Get all peer requests organized by email"""
                if self._requests_cache is None:
                    try:
                        requests_data = (
                            self._sync.peers_manager.check_all_peer_requests(
                                verbose=False
                            )
                        )
                        # Group by email
                        by_email = {}
                        for transport_key, reqs in requests_data.items():
                            for req in reqs:
                                if req.email not in by_email:
                                    by_email[req.email] = {
                                        "email": req.email,
                                        "transports": [],
                                        "platforms": [],
                                    }
                                by_email[req.email]["transports"].append(req.transport)
                                by_email[req.email]["platforms"].append(req.platform)
                        self._requests_cache = by_email
                    except:
                        self._requests_cache = {}
                return self._requests_cache

            def __getitem__(self, key):
                """Access requests by index or email"""
                all_requests = self._get_all_requests()

                if isinstance(key, int):
                    # Index access: requests[0]
                    emails = sorted(all_requests.keys())
                    if 0 <= key < len(emails):
                        email = emails[key]
                        return all_requests[email]
                    else:
                        raise IndexError(f"Request index {key} out of range")
                elif isinstance(key, str):
                    # Email access: requests['email@example.com']
                    if key in all_requests:
                        return all_requests[key]
                    else:
                        raise KeyError(f"No peer request from '{key}'")
                else:
                    raise TypeError(f"Invalid key type: {type(key)}")

            def __repr__(self):
                # Get peer requests
                all_requests = self._get_all_requests()
                total = len(all_requests)

                if total == 0:
                    return "No pending peer requests"

                # Build string representation
                lines = [f"Peer Requests ({total}):"]

                # Display each unique email
                for email in sorted(all_requests.keys()):
                    data = all_requests[email]
                    transports_str = ", ".join(sorted(set(data["transports"])))
                    lines.append(f"  • {email} (via {transports_str})")

                lines.append("\nAccept with: client.add_peer('email')")
                return "\n".join(lines)

            def __len__(self):
                return len(self._get_all_requests())

            def __iter__(self):
                """Allow iteration over request emails"""
                return iter(sorted(self._get_all_requests().keys()))

            def list(self):
                """Get list of unique emails with pending requests"""
                return sorted(self._get_all_requests().keys())

            def check(self):
                """Manually check for new peer requests"""
                self._requests_cache = None  # Clear cache
                return self._sync.peers_manager.check_all_peer_requests(verbose=True)

        return PeerRequestsProperty(self._sync)

    def __repr__(self):
        """Display peers and peer requests in a compact format"""
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        from io import StringIO

        # Create string buffer for rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=75)

        # Get peers and peer requests
        peers_list = self._sync.peers

        # Check for peer requests
        try:
            peer_requests_data = self._sync.peers_manager.check_all_peer_requests(
                verbose=False
            )
            # Flatten to unique emails
            peer_requests = set()
            for transport_key, requests in peer_requests_data.items():
                for request in requests:
                    peer_requests.add(request.email)
            peer_requests = sorted(list(peer_requests))
        except:
            peer_requests = []

        # Build content lines
        lines = []

        # Peers section
        if peers_list:
            lines.append(
                Text("client.peers", style="bold green")
                + Text(f"  [0] or ['email']", style="dim")
            )
            for i, email in enumerate(peers_list):
                peer = self._sync.peers_manager.get_peer(email)
                if peer:
                    verified_transports = peer.get_verified_transports()
                    transports_str = (
                        ", ".join(verified_transports)
                        if verified_transports
                        else "none"
                    )
                    lines.append(
                        Text(f"  [{i}] {email:<28} ✓ {transports_str}", style="")
                    )
        else:
            lines.append(
                Text("client.peers", style="bold green") + Text("  None", style="dim")
            )

        # Separator
        if peers_list and peer_requests:
            lines.append(Text(""))

        # Requests section
        if peer_requests:
            lines.append(
                Text("client.peers.requests", style="bold yellow")
                + Text(f"  [0] or ['email']", style="dim")
            )
            for i, email in enumerate(peer_requests):
                # Find which transports the request came from
                request_transports = []
                for transport_key, requests in peer_requests_data.items():
                    for request in requests:
                        if request.email == email:
                            request_transports.append(request.transport)

                transports_str = (
                    ", ".join(set(request_transports)) if request_transports else "?"
                )
                lines.append(
                    Text(f"  [{i}] {email:<28} ⏳ via {transports_str}", style="")
                )
        elif peers_list:
            if lines:
                lines.append(Text(""))
            lines.append(
                Text("client.peers.requests", style="bold yellow")
                + Text("  None", style="dim")
            )

        # Empty state
        if not peers_list and not peer_requests:
            lines.append(
                Text("No peers yet. ", style="dim")
                + Text("Add with: client.add_peer('email')", style="dim italic")
            )

        # Create panel with all lines
        content = Text("\n").join(lines)
        title = Text("Peers & Requests", style="bold") + Text(
            f"  ({len(peers_list)} active, {len(peer_requests)} pending)",
            style="dim",
        )

        panel = Panel(
            content,
            title=title,
            title_align="left",
            padding=(1, 2),
            expand=False,
        )

        console.print(panel)
        return string_buffer.getvalue().strip()
