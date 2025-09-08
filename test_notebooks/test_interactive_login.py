#!/usr/bin/env python3
"""
Interactive test for syft-client login
This should be run in an interactive terminal
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syft_client import login

def main():
    print("=== Interactive Login Test ===\n")
    
    # Check if running interactively
    if not sys.stdin.isatty():
        print("❌ This test must be run in an interactive terminal")
        print("Please run this script directly from the terminal:")
        print("  cd /Users/atrask/Desktop/Laboratory/syft-client")
        print("  uv run test_notebooks/test_interactive_login.py")
        return
    
    email = "liamtrask@gmail.com"
    print(f"Testing interactive login for {email}")
    print("Note: This will prompt you for your Gmail app password if needed.\n")
    
    try:
        result = login(email)
        print("\n" + "="*60)
        print("✅ LOGIN SUCCESSFUL!")
        print(f"Result: {result}")
        print("="*60)
        
        # Test a second login to verify credential caching works
        print("\n\nTesting cached credentials (should not prompt for password)...")
        result2 = login(email)
        print("\n" + "="*60)
        print("✅ CACHED LOGIN SUCCESSFUL!")
        print(f"Result: {result2}")
        print("="*60)
        
    except Exception as e:
        print(f"\n❌ Login failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()