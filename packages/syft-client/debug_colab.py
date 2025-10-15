"""Debug script to find where the 403 warning is coming from in Colab"""

# First, let's patch the googleapiclient logger to add a stack trace
import logging
import traceback
import sys

# Create a custom handler that shows stack traces
class StackTraceHandler(logging.Handler):
    def emit(self, record):
        if "403 Forbidden" in str(record.getMessage()):
            print("\n" + "="*80)
            print(f"WARNING FOUND: {record.getMessage()}")
            print("\nStack trace:")
            for line in traceback.format_stack()[:-1]:
                print(line.strip())
            print("="*80 + "\n")

# Add our handler to the googleapiclient logger
googleapi_logger = logging.getLogger('googleapiclient.http')
handler = StackTraceHandler()
handler.setLevel(logging.WARNING)
googleapi_logger.addHandler(handler)

# Now import and use syft_client
print("Importing syft_client...")
import syft_client

print("\nLogging in...")
client = syft_client.login("liamtrask@gmail.com")

print("\nNow printing client to trigger the warning...")
print(client)

print("\nDone!")

# Let's also check each transport's check_api_enabled method directly
print("\n" + "="*80)
print("Testing each transport's check_api_enabled method directly:")

transports = ['gmail', 'gdrive_files', 'gsheets', 'gforms']
for transport_name in transports:
    print(f"\nTesting {transport_name}...")
    try:
        # Get the transport class
        if transport_name == 'gmail':
            from syft_client.platforms.google_personal.gmail import GmailTransport
            transport_class = GmailTransport
        elif transport_name == 'gdrive_files':
            from syft_client.platforms.google_personal.gdrive_files import GDriveFilesTransport
            transport_class = GDriveFilesTransport
        elif transport_name == 'gsheets':
            from syft_client.platforms.google_personal.gsheets import GSheetsTransport
            transport_class = GSheetsTransport
        elif transport_name == 'gforms':
            from syft_client.platforms.google_personal.gforms import GFormsTransport
            transport_class = GFormsTransport
        
        # Call check_api_enabled
        result = transport_class.check_api_enabled(client.google_personal)
        print(f"  Result: {result}")
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*80)