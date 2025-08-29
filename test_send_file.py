#!/usr/bin/env python3
"""Test the new send_file_or_folder method"""

import syft_client as sc

# Example usage:
# client = sc.login("alice@gmail.com")
# 
# # First add a friend if not already added
# if "bob@gmail.com" not in client.friends:
#     client.add_friend("bob@gmail.com")
# 
# # Send a file (creates SyftMessage)
# success = client.send_file_or_folder("test.txt", "bob@gmail.com")
# 
# # Send a folder (creates SyftMessage with all files)
# success = client.send_file_or_folder("my_folder/", "bob@gmail.com")
# 
# # Try sending to non-friend (should error)
# success = client.send_file_or_folder("test.txt", "notafriend@gmail.com")

print("Test file created. Usage example:")
print("""
import syft_client as sc

client = sc.login("alice@gmail.com")

# Send file to existing friend (creates a SyftMessage)
client.send_file_or_folder("myfile.txt", "bob@gmail.com")
# Output: 📦 Creating message: syft_message_1234567890_abc123
#         📄 Added file: myfile.txt
#         ✅ Message sent to bob@gmail.com

# Send folder to existing friend (creates SyftMessage with all contents)
client.send_file_or_folder("my_folder/", "bob@gmail.com")
# Output: 📦 Creating message: syft_message_1234567891_def456
#         📄 Added: file1.txt
#         📄 Added: subdir/file2.txt
#         ✅ Message sent to bob@gmail.com

# Try sending to non-friend (will error)
client.send_file_or_folder("myfile.txt", "stranger@gmail.com")
# Output: ❌ We don't have an outbox for stranger@gmail.com

# Message replacement: sending again will replace the existing message
client.send_file_or_folder("myfile.txt", "bob@gmail.com")
# Output: 📦 Creating message: syft_message_1234567892_ghi789
#         📄 Added file: myfile.txt
#         ♻️ Replacing existing message: syft_message_1234567892_ghi789
#         ✅ Message sent to bob@gmail.com

# The recipient will receive a complete SyftMessage folder containing:
# - metadata.json (with minimal schema)
# - lock.json (with integrity checksum)
# - data/files/ (containing the actual files)
# - .write_lock (for concurrency control)
""")