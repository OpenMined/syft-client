#!/usr/bin/env python3
"""
Test the new SyftClient object structure
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import syft_client as sc

def test_syft_client():
    print("=== Testing SyftClient Object Structure ===\n")
    
    # Mock authentication for testing
    # In real usage, this would prompt for password
    print("Creating mock SyftClient for demonstration...")
    
    # Create a mock client without actual authentication
    from syft_client.syft_client import SyftClient
    from syft_client.platforms import get_platform_client
    from syft_client.platforms.detection import Platform
    
    # Create a client for Gmail
    email = "test@gmail.com"
    platform = Platform.GOOGLE_PERSONAL
    platform_client = get_platform_client(platform, email)
    
    # Mock auth data
    mock_auth_data = {
        'email': email,
        'auth_method': 'app_password',
        'servers': {
            'smtp': {'server': 'smtp.gmail.com', 'port': 587},
            'imap': {'server': 'imap.gmail.com', 'port': 993}
        }
    }
    
    # Create SyftClient
    client = SyftClient(email, platform_client, mock_auth_data)
    
    print(f"Gmail client: {client}")
    print(f"Gmail client repr: {repr(client)}")
    
    # Test properties
    print(f"\nClient email: {client.email}")
    print(f"Platform name: {client.platform_name}")
    print(f"Platform object: {client.platform}")
    print(f"Available transports: {client.transports}")
    
    print("\n" + "="*50 + "\n")
    
    # Create another client for Outlook
    email2 = "test@outlook.com"
    platform2 = Platform.MICROSOFT
    platform_client2 = get_platform_client(platform2, email2)
    
    mock_auth_data2 = {
        'email': email2,
        'auth_method': 'oauth2',
        'servers': {
            'smtp': {'server': 'smtp.office365.com', 'port': 587},
            'imap': {'server': 'outlook.office365.com', 'port': 993}
        }
    }
    
    client2 = SyftClient(email2, platform_client2, mock_auth_data2)
    
    print(f"Outlook client: {client2}")
    print(f"Outlook client repr: {repr(client2)}")
    
    # Test properties
    print(f"\nClient email: {client2.email}")
    print(f"Platform name: {client2.platform_name}")
    print(f"Available transports: {client2.transports}")

if __name__ == "__main__":
    test_syft_client()