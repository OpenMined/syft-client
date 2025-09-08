#!/usr/bin/env python3
"""
Debug script to test syft-wallet credential storage
"""

import syft_wallet as wallet

def test_basic_store():
    """Test basic credential storage"""
    print("Testing basic credential storage...")
    
    # Test 1: Simple name, no special characters
    print("\n1. Testing simple credentials (no special chars):")
    result = wallet.store_credentials(
        name="test_simple",
        username="user",
        password="pass123",
        tags=["test"],
        description="Simple test"
    )
    print(f"   Result: {result}")
    
    # Test 2: Email as username
    print("\n2. Testing with email username:")
    result = wallet.store_credentials(
        name="test_email",
        username="user@example.com",
        password="pass123",
        tags=["test"],
        description="Email test"
    )
    print(f"   Result: {result}")
    
    # Test 3: Complex password
    print("\n3. Testing with complex password:")
    result = wallet.store_credentials(
        name="test_complex_pass",
        username="user",
        password="p@ss!w0rd#123$",
        tags=["test"],
        description="Complex password test"
    )
    print(f"   Result: {result}")
    
    # Test 4: Special characters in description
    print("\n4. Testing with special chars in description:")
    result = wallet.store_credentials(
        name="test_desc",
        username="user",
        password="pass123",
        tags=["test"],
        description="Test with @ and : symbols"
    )
    print(f"   Result: {result}")
    
    # Test 5: The exact format we're using
    print("\n5. Testing exact syft-client format:")
    result = wallet.store_credentials(
        name="google_personal-test_at_gmail_com",
        username="test@gmail.com",
        password="abcdefghijklmnop",  # 16 char app password
        tags=["email", "google_personal", "syft-client"],
        description="google_personal email account for syft-client"
    )
    print(f"   Result: {result}")


def test_with_actual_password():
    """Test with an actual app password format"""
    print("\n\n6. Testing with actual app password format:")
    
    # Google app passwords are 16 chars, lowercase letters only
    result = wallet.store_credentials(
        name="google_test_final",
        username="test@gmail.com",
        password="abcd efgh ijkl mnop".replace(" ", ""),  # Simulated app password
        tags=["email", "google_personal", "syft-client"],
        description="google_personal email account for syft-client"
    )
    print(f"   Result: {result}")


if __name__ == "__main__":
    print("=== Syft-Wallet Debug Tests ===\n")
    
    try:
        test_basic_store()
        test_with_actual_password()
    except Exception as e:
        print(f"\n❌ Exception occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n=== Tests Complete ===")