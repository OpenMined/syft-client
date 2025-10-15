"""
Receiver functionality for automatic inbox monitoring and message processing
"""

from .receiver_manager import ReceiverManager
from .receiver import create_receiver_endpoint, destroy_receiver_endpoint

__all__ = ["ReceiverManager", "create_receiver_endpoint", "destroy_receiver_endpoint"]