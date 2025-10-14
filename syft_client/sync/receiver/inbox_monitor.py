"""
Inbox monitoring and change detection for the receiver
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class InboxMonitor:
    """Monitors peer inboxes for changes and tracks state"""

    def __init__(self, state_dir: Optional[Path] = None):
        """
        Initialize inbox monitor

        Args:
            state_dir: Directory to store state files (default: ~/.syft/receiver/state)
        """
        if state_dir is None:
            state_dir = Path.home() / ".syft" / "receiver" / "state"

        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.peer_states = self._load_peer_states()
        self.processed_messages = self._load_processed_messages()

    def _load_peer_states(self) -> Dict[str, Dict]:
        """Load peer states from disk"""
        state_file = self.state_dir / "peer_states.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_peer_states(self):
        """Save peer states to disk"""
        state_file = self.state_dir / "peer_states.json"
        with open(state_file, "w") as f:
            json.dump(self.peer_states, f, indent=2)

    def _load_processed_messages(self) -> Dict[str, List[str]]:
        """Load processed message IDs from disk"""
        msg_file = self.state_dir / "processed_messages.json"
        if msg_file.exists():
            try:
                with open(msg_file, "r") as f:
                    return json.load(f)
            except:
                pass
        return {}

    def _save_processed_messages(self):
        """Save processed message IDs to disk"""
        msg_file = self.state_dir / "processed_messages.json"
        with open(msg_file, "w") as f:
            json.dump(self.processed_messages, f, indent=2)

    def get_peer_state(self, peer_email: str) -> Dict[str, Any]:
        """Get saved state for a peer"""
        return self.peer_states.get(
            peer_email,
            {
                "last_check": None,
                "last_message_id": None,
                "message_count": 0,
                "transports_checked": [],
                "content_hashes": {},
            },
        )

    def update_peer_state(self, peer_email: str, state: Dict[str, Any]):
        """Update and save peer state"""
        self.peer_states[peer_email] = state
        self._save_peer_states()

    def is_message_processed(self, peer_email: str, message_id: str) -> bool:
        """Check if a message has already been processed"""
        peer_messages = self.processed_messages.get(peer_email, [])
        return message_id in peer_messages

    def mark_message_processed(self, peer_email: str, message_id: str):
        """Mark a message as processed"""
        if peer_email not in self.processed_messages:
            self.processed_messages[peer_email] = []

        if message_id not in self.processed_messages[peer_email]:
            self.processed_messages[peer_email].append(message_id)
            # Keep only last 1000 messages per peer
            self.processed_messages[peer_email] = self.processed_messages[peer_email][
                -1000:
            ]
            self._save_processed_messages()

    def compute_content_hash(self, content: Any) -> str:
        """Compute hash of content for change detection"""
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        elif isinstance(content, (list, dict)):
            content_bytes = json.dumps(content, sort_keys=True).encode("utf-8")
        else:
            content_bytes = str(content).encode("utf-8")

        return hashlib.sha256(content_bytes).hexdigest()

    def has_peer_changed(
        self, peer_email: str, transport_name: str, current_content: Any
    ) -> bool:
        """Check if peer inbox has changed for a specific transport"""
        state = self.get_peer_state(peer_email)
        content_hashes = state.get("content_hashes", {})

        current_hash = self.compute_content_hash(current_content)
        last_hash = content_hashes.get(transport_name)

        return last_hash != current_hash

    def update_transport_hash(self, peer_email: str, transport_name: str, content: Any):
        """Update the content hash for a peer's transport"""
        state = self.get_peer_state(peer_email)
        if "content_hashes" not in state:
            state["content_hashes"] = {}

        state["content_hashes"][transport_name] = self.compute_content_hash(content)
        state["last_check"] = time.time()

        self.update_peer_state(peer_email, state)
