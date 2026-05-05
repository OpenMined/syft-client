"""Enclave runner — long-running process that drives the enclave lifecycle.

Startup sequence:
    INITIALIZING -> ATTESTING -> PEERING -> RUNNING (loop)

The RUNNING state executes a poll loop:
    sync -> receive_jobs -> run_jobs -> distribute_results -> sleep
"""

import logging
import signal
import time
from pathlib import Path
from typing import Optional

from syft_enclaves.client import SyftEnclaveClient
from syft_enclaves.state import EnclaveState, EnclaveStateMachine

logger = logging.getLogger(__name__)

HEARTBEAT_PATH = Path("/tmp/enclave_heartbeat")
TEE_SOCKET_PATH = Path("/run/container_launcher/teeserver.sock")


class EnclaveRunner:
    """State machine + poll loop for enclave operation inside a TEE container."""

    def __init__(
        self,
        client: SyftEnclaveClient,
        poll_interval: int = 10,
        require_tee: bool = False,
    ) -> None:
        self.client = client
        self.poll_interval = poll_interval
        self.require_tee = require_tee
        self._sm = EnclaveStateMachine()
        self._shutdown_requested = False

    @property
    def state(self) -> EnclaveState:
        return self._sm.state

    # -- lifecycle --------------------------------------------------------

    def run(self) -> None:
        """Main entry point. Blocks until shutdown signal."""
        self._install_signal_handlers()
        logger.info(
            "Enclave runner starting — email=%s poll=%ds",
            self.client.email,
            self.poll_interval,
        )

        try:
            self._on_initializing()
            self._sm.transition(EnclaveState.ATTESTING)
            self._on_attesting()
            self._sm.transition(EnclaveState.PEERING)
            self._on_peering()
            self._sm.transition(EnclaveState.RUNNING)
            self._loop()
        except Exception as exc:
            self._sm.fail(str(exc))
            logger.exception("Fatal error in enclave runner")
            raise
        finally:
            self._sm.transition(EnclaveState.SHUTTING_DOWN)
            self._on_shutting_down()

    # -- state handlers ---------------------------------------------------

    def _on_initializing(self) -> None:
        """Validate configuration, ensure directories exist."""
        logger.info("Initializing enclave for %s", self.client.email)

    def _on_attesting(self) -> None:
        """Verify TEE environment and publish attestation."""
        in_tee = TEE_SOCKET_PATH.exists()
        if self.require_tee and not in_tee:
            raise RuntimeError(
                f"TEE socket not found at {TEE_SOCKET_PATH}. "
                "Set require_tee=False for local testing."
            )
        if in_tee:
            logger.info("Confidential Spaces TEE detected")
        else:
            logger.warning("Running outside TEE — attestation unavailable")

    def _on_peering(self) -> None:
        """Load peers and accept pending peer requests."""
        self.client.load_peers()
        self._accept_peers()
        self.client.sync()
        logger.info("Initial peer sync complete — %d peers", len(self.client.peers))

    def _on_shutting_down(self) -> None:
        logger.info("Enclave runner shut down")

    # -- main loop --------------------------------------------------------

    def _loop(self) -> None:
        """Core poll loop — runs until shutdown is requested."""
        logger.info("Entering main loop (interval=%ds)", self.poll_interval)
        while not self._shutdown_requested:
            self._tick()
            self._write_heartbeat()
            self._sleep()

    def _tick(self) -> None:
        """Single iteration of the main loop."""
        try:
            self._accept_peers()
            self.client.sync()
            self.client.receive_jobs()
            self.client.run_jobs()
            self.client.distribute_results()
        except Exception:
            logger.exception("Error during tick")
            # Don't crash — log and retry next cycle

    def _accept_peers(self) -> None:
        """Accept any pending peer requests."""
        self.client.load_peers()
        for peer in self.client.peers:
            if getattr(peer, "state", None) == "requested_by_peer":
                try:
                    self.client.approve_peer_request(peer.email)
                    logger.info("Accepted peer: %s", peer.email)
                except Exception:
                    logger.warning(
                        "Failed to accept peer: %s", peer.email, exc_info=True
                    )

    # -- utilities --------------------------------------------------------

    def _write_heartbeat(self) -> None:
        try:
            HEARTBEAT_PATH.write_text(str(time.time()))
        except OSError:
            pass

    def _sleep(self) -> None:
        """Interruptible sleep — exits early on shutdown."""
        end = time.monotonic() + self.poll_interval
        while time.monotonic() < end and not self._shutdown_requested:
            time.sleep(0.5)

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: Optional[object]) -> None:
        name = signal.Signals(signum).name
        logger.info("Received %s — requesting shutdown", name)
        self._shutdown_requested = True
