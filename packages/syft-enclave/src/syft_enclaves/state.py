"""Enclave runner state machine."""

import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class EnclaveState(str, Enum):
    INITIALIZING = "initializing"
    ATTESTING = "attesting"
    PEERING = "peering"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"
    ERROR = "error"


# Valid state transitions
_TRANSITIONS: dict[EnclaveState, set[EnclaveState]] = {
    EnclaveState.INITIALIZING: {EnclaveState.ATTESTING, EnclaveState.ERROR},
    EnclaveState.ATTESTING: {EnclaveState.PEERING, EnclaveState.ERROR},
    EnclaveState.PEERING: {EnclaveState.RUNNING, EnclaveState.ERROR},
    EnclaveState.RUNNING: {EnclaveState.SHUTTING_DOWN, EnclaveState.ERROR},
    EnclaveState.ERROR: {EnclaveState.INITIALIZING, EnclaveState.SHUTTING_DOWN},
    EnclaveState.SHUTTING_DOWN: set(),
}


class InvalidTransitionError(Exception):
    pass


class EnclaveStateMachine:
    """Tracks enclave state with validated transitions."""

    def __init__(self) -> None:
        self._state = EnclaveState.INITIALIZING
        self._error: Optional[str] = None

    @property
    def state(self) -> EnclaveState:
        return self._state

    @property
    def error(self) -> Optional[str]:
        return self._error

    def transition(self, new_state: EnclaveState) -> None:
        allowed = _TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self._state} to {new_state}. "
                f"Allowed: {allowed}"
            )
        logger.info("State: %s -> %s", self._state, new_state)
        self._state = new_state
        if new_state != EnclaveState.ERROR:
            self._error = None

    def fail(self, reason: str) -> None:
        logger.error("Entering ERROR state: %s", reason)
        self._error = reason
        self._state = EnclaveState.ERROR
