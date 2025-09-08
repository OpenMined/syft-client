#!/usr/bin/env python3
"""
Test SyftClient with multiple platforms for same email
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from syft_client.syft_client import SyftClient
from syft_client.platforms import get_platform_client
from syft_client.platforms.detection import Platform

def test_multi_platform_client():
    print("=== Testing SyftClient with Multiple Platforms ===\n")
    
    # Same email for multiple services
    email = "user@example.com"
    
    # Create SyftClient for this email
    client = SyftClient(email)
    print(f"New client for {email}: {client}")
    print(f"Platforms: {client.platform_names}\n")
    
    # Add Gmail platform
    print("Adding Gmail platform...")
    gmail_platform = get_platform_client(Platform.GOOGLE_PERSONAL, email)
    gmail_auth = {
        'email': email,
        'auth_method': 'app_password',
        'servers': {
            'smtp': {'server': 'smtp.gmail.com', 'port': 587},
            'imap': {'server': 'imap.gmail.com', 'port': 993}
        }
    }
    client.add_platform(gmail_platform, gmail_auth)
    
    print(f"\nClient after adding Gmail:")
    print(client)
    print(f"Platform names: {client.platform_names}")
    
    # Add Dropbox platform (same email!)
    print("\n\nAdding Dropbox platform...")
    dropbox_platform = get_platform_client(Platform.DROPBOX, email)
    dropbox_auth = {
        'email': email,
        'auth_method': 'oauth2',
        'access_token': 'fake_dropbox_token'
    }
    client.add_platform(dropbox_platform, dropbox_auth)
    
    print(f"\nClient after adding Dropbox:")
    print(client)
    print(f"Platform names: {client.platform_names}")
    
    # Add Microsoft platform (same email again!)
    print("\n\nAdding Microsoft platform...")
    microsoft_platform = get_platform_client(Platform.MICROSOFT, email)
    microsoft_auth = {
        'email': email,
        'auth_method': 'oauth2',
        'servers': {
            'smtp': {'server': 'smtp.office365.com', 'port': 587},
            'imap': {'server': 'outlook.office365.com', 'port': 993}
        }
    }
    client.add_platform(microsoft_platform, microsoft_auth)
    
    print(f"\nClient after adding Microsoft:")
    print(client)
    print(f"Platform names: {client.platform_names}")
    
    # Access specific platforms and their transports
    print("\n\n=== Accessing Specific Platforms ===")
    
    for platform_name in client.platform_names:
        platform = client.get_platform(platform_name)
        transports = client.get_transports(platform_name)
        print(f"\n{platform_name}:")
        print(f"  Platform object: {platform}")
        print(f"  Transports: {transports}")
    
    # Show all transports at once
    print("\n\n=== All Transports ===")
    all_transports = client.all_transports
    for platform, transports in all_transports.items():
        print(f"{platform}: {len(transports)} transports")
    
    print(f"\n\nFinal client representation:")
    print(f"str(): {client}")
    print(f"repr(): {repr(client)}")

if __name__ == "__main__":
    test_multi_platform_client()