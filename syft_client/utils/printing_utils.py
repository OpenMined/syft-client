from typing import List
from syft_client.environment import Environment
import sys
import time


class LoginProgressPrinter:
    def __init__(self, environment: Environment, verbose: bool, total_steps: int):
        self.environment = environment
        self.verbose = verbose
        self.total_steps = total_steps

    def print_colab(self, message: str):
        from IPython.display import clear_output

        clear_output(wait=True)
        print(message)

    def print_terminal_jupyter(self, step: int, message: str):
        sys.stdout.write(f"\r[{step}/{self.total_steps}] {message}...{' ' * 40}\r")
        sys.stdout.flush()
        # Small delay to make progress visible
        time.sleep(0.1)

    def print_progress_login(
        self,
        step: int,
        message: str,
    ):
        """Print progress with environment-aware output"""
        if self.verbose:
            if self.environment == Environment.COLAB:
                self.print_colab(f"[{step}/{self.total_steps}] {message}...")
            else:
                # In terminal/Jupyter, use carriage returns for clean progress
                # Progress message with carriage return
                self.print_terminal_jupyter(step, message)
        return step + 1

    def print_final_message(self, active_transports: List[str], peer_count: int):
        active_transports_str = ", ".join(active_transports)
        if peer_count > 0:
            nr_of_peers_str = f"{peer_count} peers" if peer_count > 1 else "1 peer"
            self._print_final_message(
                f"Connected peer-to-peer to {nr_of_peers_str} via: {active_transports_str}",
            )
        else:
            self._print_final_message(
                f"Peer-to-peer ready via: {active_transports_str}",
            )

    def _print_final_message(self, message: str):
        if self.verbose:
            if self.environment == Environment.COLAB:
                self.print_colab(f"✅ {message}")
            else:
                # In terminal/Jupyter, use carriage returns for clean progress
                # Clear the line first, then print final message
                sys.stdout.write(f"\r{' ' * 80}\r")
                sys.stdout.flush()
                print(f"✅ {message}")
