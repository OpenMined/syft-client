"""Test transport setup directly"""
from syft_client.platforms.google_org.gdrive_files import GDriveFilesTransport
from syft_client.environment import Environment

# Create a transport instance
transport = GDriveFilesTransport("test@gmail.com")
print(f"Transport environment: {transport.environment}")
print(f"Is Colab: {transport.environment == Environment.COLAB}")

# Try setup with None credentials
try:
    result = transport.setup(None)
    print(f"Setup result: {result}")
    print(f"Is setup: {transport.is_setup()}")
except Exception as e:
    print(f"Setup failed: {e}")
    import traceback
    traceback.print_exc()