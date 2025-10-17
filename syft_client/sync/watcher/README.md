# SyftClient File Watcher

The file watcher provides automatic synchronization of files between peers by monitoring your SyftBox directory for changes.

## Features

- **Automatic file synchronization**: Monitors your SyftBox directory and sends changes to all peers
- **Bidirectional sync**: Also polls inbox for messages from peers
- **Echo prevention**: Smart detection prevents infinite sync loops
- **Persistent process**: Runs as a separate syft-serve process that survives Python restarts
- **Transport selection**: Automatically chooses the best transport for each file

## Quick Start

```python
import syft_client as sc

# Login
client = sc.login("your_email@gmail.com")

# Start the watcher
client.start_watcher()

# Check status
client._watcher_manager.status()

# Stop the watcher
client._watcher_manager.stop()
```

## How It Works

1. **File Monitoring**: Uses `watchdog` to monitor `~/SyftBox/datasites/{email}/` for file changes
2. **Event Processing**: When files are created/modified/deleted, events are processed
3. **Echo Prevention**: Checks sync history to avoid processing files that were just received
4. **Automatic Sending**: Sends files to all configured peers using the best available transport
5. **Inbox Polling**: Periodically checks all peer inboxes for new messages
6. **Process Isolation**: Runs as a separate syft-serve endpoint for reliability

## Directory Structure

```
SyftBox/
├── datasites/
│   └── your_email@example.com/    # Watched directory
│       ├── data.csv               # Your files
│       └── project/               # Your folders
└── .syft_sync/
    └── history/                   # Sync history for echo prevention
        └── {file_hash}/
            ├── metadata.json
            └── {message_id}.json
```

## Configuration

Environment variables:

- `SYFT_SYNC_ECHO_THRESHOLD`: Seconds to wait before considering a file as new (default: 60)
- `SYFT_INBOX_POLL_INTERVAL`: Seconds between inbox checks (default: 30)

## Implementation Details

The watcher is implemented using:

- **syft-serve**: Creates persistent server endpoints
- **watchdog**: Monitors file system events
- **Threading**: Inbox polling runs in a separate thread
- **JSON storage**: Sync history stored as JSON files

## Limitations

- Currently watches the entire `datasites/{email}` directory
- Custom paths and exclude patterns not yet implemented
- Deletion sync not yet implemented
- No real-time notifications (uses polling)
