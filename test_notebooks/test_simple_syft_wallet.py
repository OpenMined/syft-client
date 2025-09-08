#!/usr/bin/env python3
"""
Simple syft-wallet test with minimal parameters
"""

import syft_wallet as wallet

# Test 1: Simplest possible store
print("Test 1: Simplest store_credentials")
result = wallet.store_credentials(
    name="test_simple",
    username="user@example.com",
    password="password123"
)
print(f"Result: {result}\n")

# Test 2: With basic tags
print("Test 2: With tags")
result = wallet.store_credentials(
    name="test_with_tags",
    username="user@example.com",
    password="password123",
    tags=["test", "email"]
)
print(f"Result: {result}\n")

# Test 3: The exact format we're using for google_personal
print("Test 3: Google personal format")
result = wallet.store_credentials(
    name="google_personal-test_at_gmail_com",
    username="test@gmail.com",
    password="abcdefghijklmnop",
    tags=["email", "google_personal", "syftclient"],
    description="google_personal email account"
)
print(f"Result: {result}\n")