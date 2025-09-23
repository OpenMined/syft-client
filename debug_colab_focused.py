"""Debug script to find the 403 warning in google_personal only"""

import logging
import traceback

# Patch the logger to show which line is causing the warning
original_log = logging.getLogger('googleapiclient.http').warning

def patched_warning(msg, *args, **kwargs):
    if "403 Forbidden" in str(msg):
        print(f"\n🔍 WARNING LOCATION FOUND:")
        print(f"Message: {msg}")
        print("\nCall stack (most recent first):")
        
        # Get the call stack
        stack = traceback.extract_stack()
        
        # Find the first non-logging frame
        for i, frame in enumerate(stack[-10:]):  # Look at last 10 frames
            if 'logging' not in frame.filename and 'googleapiclient' not in frame.filename:
                print(f"\n  → {frame.filename}:{frame.lineno}")
                print(f"    In function: {frame.name}")
                print(f"    Line: {frame.line}")
        
    original_log(msg, *args, **kwargs)

logging.getLogger('googleapiclient.http').warning = patched_warning

# Now test
print("Testing google_personal login...")
import syft_client

client_personal = syft_client.login("liamtrask@gmail.com")
print("\nPrinting google_personal client:")
print(client_personal.google_personal)

print("\n" + "="*50 + "\n")

# Also test google_org to confirm no warning
print("Testing google_org login...")
client_org = syft_client.login("andrew@openmined.org", provider="google_org")
print("\nPrinting google_org client:")
print(client_org.google_org)

# Let's also check if it's happening during transport initialization
print("\n" + "="*50 + "\n")
print("Checking if warning happens during transport method calls...")

# Try accessing each transport
for attr in ['gmail', 'gdrive_files', 'gsheets', 'gforms']:
    print(f"\nAccessing google_personal.{attr}...")
    try:
        transport = getattr(client_personal.google_personal, attr)
        print(f"  Type: {type(transport)}")
    except Exception as e:
        print(f"  Error: {e}")