from syft_client.environment import Environment
import sys
import time


def print_progress(
    environment: Environment,
    step: int,
    total_steps: int,
    message: str,
    is_final: bool = False,
    verbose: bool = True,
):
    """Print progress with environment-aware output"""
    if verbose:
        if environment == Environment.COLAB:
            # In Colab, use clear_output for updating progress
            from IPython.display import clear_output

            clear_output(wait=True)
            if is_final:
                print(f"✅ {message}")
            else:
                print(f"[{step}/{total_steps}] {message}...")
        else:
            # In terminal/Jupyter, use carriage returns for clean progress
            if is_final:
                # Clear the line first, then print final message
                sys.stdout.write(f"\r{' ' * 80}\r")
                sys.stdout.flush()
                print(f"✅ {message}")
            else:
                # Progress message with carriage return
                sys.stdout.write(f"\r[{step}/{total_steps}] {message}...{' ' * 40}\r")
                sys.stdout.flush()
                # Small delay to make progress visible
                time.sleep(0.1)
