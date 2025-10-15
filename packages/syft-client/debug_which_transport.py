"""Quick test to see which transport is causing the 403 warning"""

import logging

# Temporarily suppress the warning to test one by one
googleapi_logger = logging.getLogger('googleapiclient.http')
original_level = googleapi_logger.level

import syft_client

# Test each transport's check_api_enabled individually
client = syft_client.login("liamtrask@gmail.com")

transports = [
    ('gdrive_files', 'GDriveFilesTransport'),
    ('gsheets', 'GSheetsTransport'),
]

for transport_name, class_name in transports:
    print(f"\n{'='*50}")
    print(f"Testing {transport_name}...")
    
    # Enable logging for this test
    googleapi_logger.setLevel(logging.WARNING)
    
    try:
        module = __import__(f'syft_client.platforms.google_personal.{transport_name}', fromlist=[class_name])
        transport_class = getattr(module, class_name)
        
        print(f"Calling check_api_enabled for {transport_name}...")
        result = transport_class.check_api_enabled(client.google_personal)
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Disable logging again
    googleapi_logger.setLevel(logging.ERROR)

print(f"\n{'='*50}")
print("\nNow testing the full repr (should show warning):")
googleapi_logger.setLevel(logging.WARNING)
print(client.google_personal)