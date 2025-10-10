"""
Transport negotiation system that selects the best transport based on multiple factors
"""

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from .peer_model import Peer
from .transport_capabilities import (
    TRANSPORT_CAPABILITIES,
    TransportCapabilities,
    TransportRequirements,
    get_transport_capabilities,
)

if TYPE_CHECKING:
    from ..syft_client import SyftClient


@dataclass
class TransportScore:
    """Score for a transport option"""

    transport_name: str
    score: float
    reasons: List[str]
    estimated_latency_ms: float

    def __repr__(self):
        return f"TransportScore({self.transport_name}, score={self.score:.2f}, latency={self.estimated_latency_ms:.0f}ms)"


class TransportNegotiator:
    """Negotiates the best transport to use based on requirements and contact capabilities"""

    def __init__(self, client: "SyftClient"):
        self.client = client

    def select_transport(
        self,
        peer: Peer,
        file_size: int,
        requested_latency_ms: Optional[int] = None,
        priority: str = "normal",
    ) -> Optional[str]:
        """
        Select the best transport for sending to a contact

        Args:
            peer: The peer to send to
            file_size: Size of the file in bytes
            requested_latency_ms: Desired latency in milliseconds
            priority: "urgent", "normal", or "background"

        Returns:
            The name of the best transport, or None if no suitable transport found
        """
        # Create requirements
        requirements = TransportRequirements(
            file_size=file_size,
            requested_latency_ms=requested_latency_ms,
            priority=priority,
        )

        # Get available transports for this peer
        available_transports = self._get_available_transports(peer)

        if not available_transports:
            if self.client.verbose:
                print(f"⚠️  No available transports for {peer.email}")
            return None

        # Score each transport
        scores = []
        for transport_name in available_transports:
            score = self._score_transport(transport_name, peer, requirements)
            if score:
                scores.append(score)

        if not scores:
            if self.client.verbose:
                print(f"⚠️  No suitable transports found for requirements")
            return None

        # Sort by score (highest first)
        scores.sort(key=lambda s: s.score, reverse=True)

        # Log decision if verbose
        if self.client.verbose:
            print(f"\n🔄 Transport negotiation for {peer.email}:")
            print(f"   File size: {self._format_size(file_size)}")
            if requested_latency_ms:
                print(f"   Requested latency: {requested_latency_ms}ms")
            print(f"   Priority: {priority}")
            print(f"\n   Scores:")
            for score in scores[:3]:  # Show top 3
                print(
                    f"   - {score.transport_name}: {score.score:.2f} (est. {score.estimated_latency_ms:.0f}ms)"
                )
                for reason in score.reasons[:2]:  # Show top 2 reasons
                    print(f"     • {reason}")

        # Return the best transport
        best = scores[0]
        if self.client.verbose:
            print(f"\n   ✅ Selected: {best.transport_name}")

        return best.transport_name

    def _get_available_transports(self, peer: Peer) -> List[str]:
        """Get list of transports available for both us and the peer"""
        # Get our available transports
        our_transports = set()

        # Check what platforms we have
        if hasattr(self.client, "_platforms"):
            for platform_name, platform in self.client._platforms.items():
                # Get all transport attributes from the platform
                for attr_name in dir(platform):
                    if not attr_name.startswith("_"):  # Skip private attributes
                        attr = getattr(platform, attr_name, None)
                        if attr and hasattr(attr, "send_to"):
                            # This looks like a transport with send_to method
                            our_transports.add(attr_name)

        # Get peer's available transports
        peer_transports = set(peer.available_transports.keys())

        # Return intersection (transports both parties have)
        return list(our_transports & peer_transports)

    def _score_transport(
        self, transport_name: str, peer: Peer, requirements: TransportRequirements
    ) -> Optional[TransportScore]:
        """Score a transport based on how well it meets requirements"""
        # Get transport capabilities
        capabilities = get_transport_capabilities(transport_name)
        if not capabilities:
            return None

        # Check if transport meets hard requirements
        if not requirements.matches_capabilities(capabilities):
            return None

        score = 0.0
        reasons = []

        # 1. Latency scoring (40% weight)
        latency_score = self._score_latency(
            transport_name, peer, requirements, capabilities
        )
        score += latency_score["score"] * 0.4
        reasons.extend(latency_score["reasons"])
        estimated_latency = latency_score["estimated_latency"]

        # 2. Reliability scoring (30% weight)
        reliability_score = self._score_reliability(transport_name, peer)
        score += reliability_score["score"] * 0.3
        reasons.extend(reliability_score["reasons"])

        # 3. Efficiency scoring (20% weight)
        efficiency_score = self._score_efficiency(
            transport_name, requirements, capabilities
        )
        score += efficiency_score["score"] * 0.2
        reasons.extend(efficiency_score["reasons"])

        # 4. Recency scoring (10% weight)
        recency_score = self._score_recency(transport_name, peer)
        score += recency_score["score"] * 0.1
        reasons.extend(recency_score["reasons"])

        return TransportScore(
            transport_name=transport_name,
            score=score,
            reasons=reasons,
            estimated_latency_ms=estimated_latency,
        )

    def _score_latency(
        self,
        transport_name: str,
        peer: Peer,
        requirements: TransportRequirements,
        capabilities: TransportCapabilities,
    ) -> Dict:
        """Score based on latency requirements"""
        score = 0.0
        reasons = []

        # Get historical latency if available
        if transport_name in peer.transport_stats:
            stats = peer.transport_stats[transport_name]
            if stats.success_count > 0:
                estimated_latency = stats.avg_latency_ms
                reasons.append(f"Historical avg: {estimated_latency:.0f}ms")
            else:
                estimated_latency = capabilities.typical_latency_ms
        else:
            estimated_latency = capabilities.typical_latency_ms

        # Score based on requirements
        if requirements.requested_latency_ms:
            if estimated_latency <= requirements.requested_latency_ms:
                score = 1.0
                reasons.append("Meets latency requirement")
            else:
                # Partial score based on how close we are
                ratio = requirements.requested_latency_ms / estimated_latency
                score = max(0, ratio)
                reasons.append(
                    f"Latency {estimated_latency:.0f}ms vs requested {requirements.requested_latency_ms}ms"
                )
        else:
            # No specific requirement, score based on speed
            if estimated_latency <= 1000:  # Sub-second
                score = 1.0
                reasons.append("Sub-second latency")
            elif estimated_latency <= 5000:  # Under 5 seconds
                score = 0.7
                reasons.append("Fast latency (<5s)")
            else:
                score = 0.4
                reasons.append("Standard latency")

        # Adjust for priority
        if requirements.priority == "urgent" and estimated_latency > 2000:
            score *= 0.5
            reasons.append("Penalized for urgent priority")
        elif requirements.priority == "background":
            score = 0.8  # Latency less important for background
            reasons.append("Background priority - latency less critical")

        return {
            "score": score,
            "reasons": reasons,
            "estimated_latency": estimated_latency,
        }

    def _score_reliability(self, transport_name: str, peer: Peer) -> Dict:
        """Score based on historical reliability"""
        score = 0.5  # Default for unknown
        reasons = []

        if transport_name in peer.transport_stats:
            stats = peer.transport_stats[transport_name]
            total = stats.success_count + stats.failure_count

            if total > 0:
                success_rate = stats.success_count / total
                score = success_rate

                if success_rate >= 0.95:
                    reasons.append(f"Excellent reliability ({success_rate:.0%})")
                elif success_rate >= 0.8:
                    reasons.append(f"Good reliability ({success_rate:.0%})")
                else:
                    reasons.append(f"Poor reliability ({success_rate:.0%})")

                # Recent failures impact
                if stats.last_failure and stats.last_success:
                    if stats.last_failure > stats.last_success:
                        score *= 0.8
                        reasons.append("Recent failure")
            else:
                reasons.append("No history - using default")
        else:
            # Bonus for verified transports
            if transport_name in peer.available_transports:
                if peer.available_transports[transport_name].verified:
                    score = 0.7
                    reasons.append("Verified transport")
                else:
                    reasons.append("Unverified transport")

        return {"score": score, "reasons": reasons}

    def _score_efficiency(
        self,
        transport_name: str,
        requirements: TransportRequirements,
        capabilities: TransportCapabilities,
    ) -> Dict:
        """Score based on efficiency for the file size"""
        score = 0.5
        reasons = []

        # Size efficiency
        if capabilities.max_file_size:
            # How well does file size fit?
            usage_ratio = requirements.file_size / capabilities.max_file_size

            if usage_ratio < 0.1:
                # Very small file for this transport
                if transport_name == "gdrive_files":
                    score = 0.3  # Overkill
                    reasons.append("File too small - inefficient")
                else:
                    score = 0.9
                    reasons.append("Efficient for small files")
            elif usage_ratio < 0.5:
                score = 1.0
                reasons.append("Optimal size range")
            elif usage_ratio < 0.9:
                score = 0.8
                reasons.append("Good size fit")
            else:
                score = 0.4
                reasons.append("Near size limit")
        else:
            # No size limit
            if requirements.file_size > 100 * 1024 * 1024:  # >100MB
                score = 1.0
                reasons.append("Good for large files")
            else:
                score = 0.7
                reasons.append("Standard efficiency")

        # Special handling for sheets
        if transport_name == "gsheets":
            if requirements.file_size <= 10_000:
                score = 1.0
                reasons.append("Perfect for tiny files")
            elif requirements.file_size <= 37_500:
                score = 0.8
                reasons.append("Good for small files")
            else:
                score = 0.0
                reasons.append("Too large for sheets")

        return {"score": score, "reasons": reasons}

    def _score_recency(self, transport_name: str, peer: Peer) -> Dict:
        """Score based on how recently the transport was used successfully"""
        score = 0.5
        reasons = []

        if transport_name in peer.transport_stats:
            stats = peer.transport_stats[transport_name]
            if stats.last_success:
                # Calculate hours since last success
                hours_ago = (time.time() - stats.last_success.timestamp()) / 3600

                if hours_ago < 1:
                    score = 1.0
                    reasons.append("Used in last hour")
                elif hours_ago < 24:
                    score = 0.8
                    reasons.append("Used today")
                elif hours_ago < 168:  # 1 week
                    score = 0.6
                    reasons.append("Used this week")
                else:
                    score = 0.4
                    reasons.append("Not recently used")
        else:
            reasons.append("Never used before")

        return {"score": score, "reasons": reasons}

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}TB"


__all__ = ["TransportNegotiator", "TransportScore"]
