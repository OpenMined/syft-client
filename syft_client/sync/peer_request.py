"""
Peer request model for tracking incoming peer requests
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class PeerRequest:
    """Represents an incoming peer request from another user"""

    email: str
    platform: str  # e.g. "google_personal", "google_org"
    transport: str  # e.g. "gdrive_files", "gsheets"
    shared_resources: List[Dict[str, Any]] = field(
        default_factory=list
    )  # What they've shared
    request_date: Optional[datetime] = None
    status: str = "pending"  # "pending", "accepted", "rejected"

    def __repr__(self) -> str:
        """Pretty representation of peer request"""
        resource_count = len(self.shared_resources)
        resource_str = f"{resource_count} resource{'s' if resource_count != 1 else ''}"

        # Format the date if available
        date_str = ""
        if self.request_date:
            # Calculate time ago
            time_diff = datetime.now() - self.request_date
            if time_diff.days > 0:
                date_str = (
                    f" ({time_diff.days} day{'s' if time_diff.days != 1 else ''} ago)"
                )
            elif time_diff.seconds > 3600:
                hours = time_diff.seconds // 3600
                date_str = f" ({hours} hour{'s' if hours != 1 else ''} ago)"
            else:
                minutes = time_diff.seconds // 60
                date_str = f" ({minutes} minute{'s' if minutes != 1 else ''} ago)"

        return f"PeerRequest(from='{self.email}', via={self.platform}.{self.transport}, {resource_str}{date_str})"


__all__ = ["PeerRequest"]
