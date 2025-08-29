# Syft-Client API Reference

Complete API documentation for syft-client v0.1.4

## Table of Contents

- [Authentication Functions](#authentication-functions)
- [GDriveUnifiedClient](#gdriveunifiedclient)
- [SyftFileBackedView](#syftfilebackedview)
- [SyftMessage](#syftmessage)
- [Utility Functions](#utility-functions)

---

## Authentication Functions

### `login(email, credentials_file="credentials.json", verbose=True, force_relogin=False)`

Authenticate and create a Google Drive client.

**Parameters:**
- `email` (str): Email address to authenticate as
- `credentials_file` (str, optional): Path to credentials.json file. Default: "credentials.json"
- `verbose` (bool, optional): Print status messages. Default: True
- `force_relogin` (bool, optional): Force fresh authentication. Default: False

**Returns:**
- `GDriveUnifiedClient`: Authenticated client instance

**Example:**
```python
import syft_client as sc

# Basic login
client = sc.login("alice@gmail.com")

# Login with custom credentials file
client = sc.login("alice@gmail.com", "my_credentials.json")

# Silent login
client = sc.login("alice@gmail.com", verbose=False)

# Force re-authentication
client = sc.login("alice@gmail.com", force_relogin=True)
```

### `logout(email)`

Remove stored credentials for an account.

**Parameters:**
- `email` (str): Email address to logout

**Returns:**
- `bool`: True if successful, False otherwise

**Example:**
```python
sc.logout("alice@gmail.com")
```

### `list_accounts()`

List all accounts with saved credentials.

**Returns:**
- `List[str]`: List of email addresses

**Example:**
```python
accounts = sc.list_accounts()
print(accounts)  # ['alice@gmail.com', 'bob@gmail.com']
```

### `wizard()`

Interactive wizard for setting up Google Drive API credentials.

**Example:**
```python
sc.wizard()  # Launches interactive setup
```

---

## GDriveUnifiedClient

Main client for Google Drive operations.

### Class Attributes

- `SCOPES` (List[str]): Google Drive API scopes
- `authenticated` (bool): Authentication status
- `my_email` (str): Authenticated user's email
- `service`: Google Drive API service instance

### Methods

#### `__init__(auth_method="auto", credentials_file="credentials.json", email=None, verbose=True, force_relogin=False)`

Initialize the client.

**Parameters:**
- `auth_method` (str): Authentication method - "auto", "colab", or "credentials"
- `credentials_file` (str): Path to credentials file
- `email` (str, optional): Email to authenticate as
- `verbose` (bool): Enable status messages
- `force_relogin` (bool): Force fresh authentication

#### `authenticate()`

Perform authentication based on configured method.

**Returns:**
- `bool`: True if successful

**Example:**
```python
client = GDriveUnifiedClient(email="alice@gmail.com")
if client.authenticate():
    print("Authenticated successfully")
```

#### `reset_syftbox()`

Delete and recreate the SyftBoxTransportService folder.

**Returns:**
- `str`: ID of the created folder

**Example:**
```python
folder_id = client.reset_syftbox()
print(f"Created SyftBox with ID: {folder_id}")
```

#### `add_friend(friend_email)`

Add a friend and set up communication channels.

**Parameters:**
- `friend_email` (str): Email address of friend to add

**Returns:**
- `bool`: True if successful

**Example:**
```python
success = client.add_friend("bob@gmail.com")
if success:
    print(f"Added bob@gmail.com as friend")
```

#### `friends` (property)

Get list of friends (people you've added).

**Returns:**
- `List[str]`: List of friend email addresses

**Example:**
```python
for friend in client.friends:
    print(f"Friend: {friend}")
```

#### `friend_requests` (property)

Get list of pending friend requests (people who added you).

**Returns:**
- `List[str]`: List of email addresses

**Example:**
```python
for request in client.friend_requests:
    print(f"Friend request from: {request}")
```

#### `create_folder(name, parent_id=None)`

Create a folder in Google Drive.

**Parameters:**
- `name` (str): Folder name
- `parent_id` (str, optional): Parent folder ID

**Returns:**
- `dict`: Folder metadata with 'id' and 'name'

**Example:**
```python
folder = client.create_folder("MyData", parent_id="parent_folder_id")
print(f"Created folder: {folder['name']} (ID: {folder['id']})")
```

#### `upload_file(file_path, folder_id=None, mime_type=None)`

Upload a file to Google Drive.

**Parameters:**
- `file_path` (str): Path to local file
- `folder_id` (str, optional): Destination folder ID
- `mime_type` (str, optional): MIME type of file

**Returns:**
- `dict`: File metadata

**Example:**
```python
file_info = client.upload_file("data.csv", folder_id="folder_id")
print(f"Uploaded: {file_info['name']}")
```

#### `download_file(file_id, destination_path)`

Download a file from Google Drive.

**Parameters:**
- `file_id` (str): Google Drive file ID
- `destination_path` (str): Local path to save file

**Returns:**
- `bool`: True if successful

**Example:**
```python
success = client.download_file("file_id", "local_data.csv")
```

#### `list_files(folder_id=None, query=None)`

List files in Google Drive.

**Parameters:**
- `folder_id` (str, optional): Folder to list files from
- `query` (str, optional): Custom query string

**Returns:**
- `List[dict]`: List of file metadata

**Example:**
```python
files = client.list_files(folder_id="folder_id")
for file in files:
    print(f"{file['name']} - {file['mimeType']}")
```

#### `delete_file(file_id)`

Delete a file or folder.

**Parameters:**
- `file_id` (str): File or folder ID to delete

**Returns:**
- `bool`: True if successful

**Example:**
```python
client.delete_file("file_id")
```

#### `share_file(file_id, email, role="reader")`

Share a file with specific permissions.

**Parameters:**
- `file_id` (str): File or folder ID
- `email` (str): Email to share with
- `role` (str): Permission role - "reader", "writer", "owner"

**Returns:**
- `dict`: Permission metadata

**Example:**
```python
permission = client.share_file("file_id", "bob@gmail.com", role="writer")
```

---

## SyftFileBackedView

Base class for file-backed storage with atomic operations and security.

### Methods

#### `__init__(path)`

Initialize file-backed view.

**Parameters:**
- `path` (Path): Base path for storage

#### `set_metadata(metadata)`

Set metadata for the object.

**Parameters:**
- `metadata` (dict): Metadata dictionary

**Example:**
```python
view = SyftFileBackedView(Path("/tmp/myobj"))
view.set_metadata({"author": "alice", "version": "1.0"})
```

#### `get_metadata()`

Get metadata for the object.

**Returns:**
- `dict`: Metadata dictionary

#### `update_metadata(updates)`

Update specific metadata fields.

**Parameters:**
- `updates` (dict): Fields to update

#### `write_data_file(filename, content)`

Write a data file with validation.

**Parameters:**
- `filename` (str): File name (validated for safety)
- `content` (bytes): File content

**Raises:**
- `ValueError`: If filename contains path traversal attempts

**Example:**
```python
view.write_data_file("data.csv", b"id,name\n1,Alice")
```

#### `read_data_file(filename)`

Read a data file.

**Parameters:**
- `filename` (str): File name to read

**Returns:**
- `bytes`: File content

#### `list_data_files()`

List all data files.

**Returns:**
- `List[Path]`: List of file paths

#### `write_json(filename, data)`

Write JSON data.

**Parameters:**
- `filename` (str): JSON file name
- `data`: JSON-serializable data

#### `read_json(filename)`

Read JSON data.

**Parameters:**
- `filename` (str): JSON file name

**Returns:**
- Deserialized JSON data

#### `lock(finalized=False, reviewer=None)`

Lock the object to prevent modifications.

**Parameters:**
- `finalized` (bool): Mark as finalized
- `reviewer` (str, optional): Reviewer identifier

#### `is_locked()`

Check if object is locked.

**Returns:**
- `bool`: Lock status

#### `calculate_checksum()`

Calculate SHA-256 checksum of all content.

**Returns:**
- `str`: Hex digest of checksum

---

## SyftMessage

Message handling for secure file transfer.

### Methods

#### `create(sender_email, recipient_email, message_root, message_type="file_transfer")`

Create a new message.

**Parameters:**
- `sender_email` (str): Sender's email
- `recipient_email` (str): Recipient's email  
- `message_root` (Path): Root directory for messages
- `message_type` (str): Type of message

**Returns:**
- `SyftMessage`: New message instance

**Example:**
```python
message = SyftMessage.create(
    sender_email="alice@gmail.com",
    recipient_email="bob@gmail.com",
    message_root=Path("/tmp/outbox")
)
```

#### `add_file(source_path, syftbox_path, permissions=None)`

Add a file to the message.

**Parameters:**
- `source_path` (Path): Path to source file
- `syftbox_path` (str): Target path in SyftBox
- `permissions` (dict, optional): Permission dictionary

**Returns:**
- `dict`: File metadata

**Example:**
```python
file_info = message.add_file(
    source_path=Path("data.csv"),
    syftbox_path="/alice@gmail.com/shared/data.csv",
    permissions={
        "read": ["bob@gmail.com"],
        "write": ["alice@gmail.com"],
        "admin": ["alice@gmail.com"]
    }
)
```

#### `get_files()`

Get list of files in message.

**Returns:**
- `List[dict]`: List of file metadata

#### `add_readme(html_content)`

Add HTML readme to message.

**Parameters:**
- `html_content` (str): HTML content

#### `finalize()`

Finalize message for sending.

**Example:**
```python
message.finalize()
print(f"Message ready: {message.is_ready}")
```

#### `validate()`

Validate message integrity.

**Returns:**
- `Tuple[bool, Optional[str]]`: (is_valid, error_message)

**Example:**
```python
is_valid, error = message.validate()
if not is_valid:
    print(f"Validation failed: {error}")
```

#### `extract_file(filename, destination)`

Extract a file from the message.

**Parameters:**
- `filename` (str): Name of file to extract
- `destination` (Path): Destination path

**Example:**
```python
message.extract_file("data.csv", Path("/tmp/extracted_data.csv"))
```

### Properties

- `message_id` (str): Unique message identifier
- `sender_email` (str): Sender's email address
- `recipient_email` (str): Recipient's email address
- `timestamp` (float): Creation timestamp
- `is_ready` (bool): Whether message is finalized
- `path` (Path): Message directory path

---

## Utility Functions

### `add_current_credentials_to_wallet(email, credentials_path)`

Add credentials to the wallet for an email.

**Parameters:**
- `email` (str): Email address
- `credentials_path` (str): Path to credentials.json

**Returns:**
- `bool`: Success status

**Example:**
```python
sc.add_current_credentials_to_wallet(
    "alice@gmail.com",
    "credentials.json"
)
```

---

## Error Handling

Common exceptions and their handling:

### Authentication Errors

```python
try:
    client = sc.login("alice@gmail.com")
except Exception as e:
    print(f"Authentication failed: {e}")
```

### API Errors

```python
from googleapiclient.errors import HttpError

try:
    client.create_folder("MyFolder")
except HttpError as e:
    if e.resp.status == 404:
        print("Folder not found")
    elif e.resp.status == 403:
        print("Permission denied")
```

### File Operation Errors

```python
try:
    message.add_file(Path("data.csv"), "/shared/data.csv")
except FileNotFoundError:
    print("Source file not found")
except ValueError as e:
    print(f"Invalid file path: {e}")
```

---

## Environment Variables

The following environment variables affect behavior:

- `SYFT_TEST_MODE`: Set to "integration" for testing mode
- `TEST_USER1_EMAIL`: Test user 1 email (testing only)
- `TEST_USER2_EMAIL`: Test user 2 email (testing only)

---

## File System Locations

Default locations for various files:

- **Wallet Directory**: `~/.syft/gdrive/`
- **Credentials**: `~/.syft/gdrive/{sanitized_email}/credentials.json`
- **Tokens**: `~/.syft/gdrive/{sanitized_email}/token.json`
- **Account Info**: `~/.syft/gdrive/{sanitized_email}/account_info.json`

Note: Email addresses are sanitized for directory names by replacing `@` with `_at_` and `.` with `_`.

---

## Best Practices

1. **Always handle authentication errors gracefully**
   ```python
   client = sc.login(email)
   if not client.authenticated:
       print("Failed to authenticate")
       return
   ```

2. **Use context managers for file operations when possible**
   ```python
   with tempfile.TemporaryDirectory() as tmpdir:
       message = SyftMessage.create(...)
   ```

3. **Validate user input before operations**
   ```python
   if "@" not in email:
       raise ValueError("Invalid email address")
   ```

4. **Clean up resources after use**
   ```python
   # Reset SyftBox when done testing
   client.reset_syftbox()
   ```

5. **Check friend requests regularly**
   ```python
   for request in client.friend_requests:
       client.add_friend(request)  # Accept all
   ```

---

## Version Information

- **Current Version**: 0.1.4
- **Python Support**: 3.8+
- **Dependencies**: 
  - google-api-python-client==2.95.0
  - google-auth==2.22.0
  - google-auth-oauthlib
  - syft-widget

---

For more examples and tutorials, see:
- [Getting Started Guide](GETTING_STARTED.md)
- [Tutorial Notebook](syft_client_tutorial.ipynb)
- [Message Tutorial](syft_message_tutorial.ipynb)