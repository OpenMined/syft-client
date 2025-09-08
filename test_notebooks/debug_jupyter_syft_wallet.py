#!/usr/bin/env python3
"""
Debug syft-wallet in Jupyter environment
"""

import subprocess
import sys
import json

# Monkey-patch subprocess to see what's happening
original_run = subprocess.run

def debug_run(cmd, *args, **kwargs):
    """Intercept and log subprocess.run calls"""
    if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == "op":
        print("\n" + "="*60)
        print("INTERCEPTED 1PASSWORD CLI COMMAND:")
        print(f"Command: {cmd}")
        print(f"Args: {args}")
        print(f"Kwargs: {kwargs}")
        
        # Show exact command string
        print("\nExact command that will be run:")
        print(" ".join(cmd))
        print("="*60 + "\n")
    
    # Call original
    result = original_run(cmd, *args, **kwargs)
    
    # Log result
    if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == "op":
        print(f"\nRESULT: returncode={result.returncode}")
        if result.stdout:
            print(f"STDOUT: {result.stdout}")
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        print("="*60 + "\n")
    
    return result

# Apply monkey patch
subprocess.run = debug_run

# Now test syft-wallet
import syft_wallet as wallet

print("Testing syft-wallet with debug enabled...\n")

# Test the simplest case
result = wallet.store_credentials(
    name="test_simple",
    username="user@example.com",
    password="password123"
)

print(f"\nFinal result: {result}")

# Restore original
subprocess.run = original_run