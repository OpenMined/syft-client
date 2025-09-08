#!/usr/bin/env python3
"""
Debug the actual authentication flow with syft-wallet
"""

import subprocess
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Store the original run function
original_run = subprocess.run

# Create a wrapper that logs all subprocess calls
def debug_run(cmd, *args, **kwargs):
    """Intercept and log subprocess.run calls"""
    if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == "op":
        print("\n" + "🔍" * 30)
        print("INTERCEPTED 1PASSWORD CLI COMMAND:")
        print("Command list:")
        for i, arg in enumerate(cmd):
            print(f"  [{i}]: {repr(arg)}")
        
        print("\nCommand as string:")
        print(f"  {' '.join(cmd)}")
        
        print("\nkwargs:")
        for k, v in kwargs.items():
            if k != 'env':  # Skip env vars for brevity
                print(f"  {k}: {v}")
        
        print("🔍" * 30 + "\n")
    
    # Call the original function
    result = original_run(cmd, *args, **kwargs)
    
    # Log the result for op commands
    if isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == "op":
        print(f"\n📊 RESULT: returncode={result.returncode}")
        if result.stdout:
            print(f"STDOUT: {result.stdout[:200]}...")
        if result.stderr:
            print(f"STDERR: {result.stderr}")
    
    return result

# Monkey-patch subprocess.run
subprocess.run = debug_run

# Now import and run the actual authentication
from syft_client import login

def test_auth_flow():
    """Test the actual authentication flow with debugging"""
    
    print("=== Testing Authentication Flow with Debugging ===\n")
    
    # Test with a gmail account
    email = "liamtrask@gmail.com"
    
    try:
        print(f"Attempting login for {email}...")
        result = login(email)
        print(f"\n✅ Login result: {result}")
    except Exception as e:
        print(f"\n❌ Login failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        test_auth_flow()
    finally:
        # Restore original subprocess.run
        subprocess.run = original_run
        print("\n=== Debug complete, subprocess.run restored ===")