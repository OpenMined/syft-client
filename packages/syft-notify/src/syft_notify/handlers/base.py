from typing import Protocol

from syft_notify.core.base import NotificationSender, StateManager


class Handler(Protocol):
    sender: NotificationSender
    state: StateManager
