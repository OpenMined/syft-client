#!/usr/bin/env python3
"""
Debug syft-wallet by intercepting the actual subprocess call
"""

import subprocess
import sys
import syft_wallet as wallet

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

def test_store_credentials():
    """Test storing credentials with debugging enabled"""
    
    print("=== Testing syft-wallet store_credentials with debugging ===\n")
    
    # Test the exact parameters that are failing
    result = wallet.store_credentials(
        name="google_personal-liamtrask_at_gmail_com",
        username="liamtrask@gmail.com",
        password="abcdefghijklmnop",  # Fake 16-char password
        tags=["email", "google_personal", "syftclient"],
        description="google_personal email account"
    )
    
    print(f"\n✅ Final result: {result}")
    
    # Also test a simpler version
    print("\n\n=== Testing simpler version ===\n")
    
    result2 = wallet.store_credentials(
        name="test_simple",
        username="test@example.com",
        password="password123",
        tags=["test"],
        description="Test item"
    )
    
    print(f"\n✅ Final result: {result2}")

def test_escaping_issues():
    """Test various characters that might need escaping"""
    
    print("\n\n=== Testing potential escaping issues ===\n")
    
    test_cases = [
        {
            "name": "test_equals",
            "username": "user=test@example.com",
            "password": "pass=word123",
            "description": "Test with = signs"
        },
        {
            "name": "test_quotes",
            "username": "user\"test@example.com",
            "password": "pass'word123",
            "description": "Test with quotes"
        },
        {
            "name": "test_spaces",
            "username": "user test@example.com",
            "password": "pass word 123",
            "description": "Test with spaces"
        },
        {
            "name": "test_newline",
            "username": "user@example.com",
            "password": "password123",
            "description": "Test with\nnewline"
        }
    ]
    
    for test in test_cases:
        print(f"\n--- Testing: {test['name']} ---")
        try:
            result = wallet.store_credentials(
                name=test["name"],
                username=test["username"],
                password=test["password"],
                tags=["test"],
                description=test["description"]
            )
            print(f"Result: {result}")
        except Exception as e:
            print(f"Exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    try:
        test_store_credentials()
        test_escaping_issues()
    except Exception as e:
        print(f"\n❌ Unhandled exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    # Restore original subprocess.run
    subprocess.run = original_run
    print("\n=== Debug complete, subprocess.run restored ===")