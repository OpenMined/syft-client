"""
Receiver functionality for automatic inbox monitoring and message processing
"""

from .receiver import create_receiver_endpoint, destroy_receiver_endpoint
from .receiver_manager import ReceiverManager

__all__ = ["ReceiverManager", "create_receiver_endpoint", "destroy_receiver_endpoint"]
