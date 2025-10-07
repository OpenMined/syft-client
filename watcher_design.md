# File Watcher Design for syft-client

## Overview
The file watcher will provide automatic synchronization of files between peers, monitoring local changes and automatically sending/receiving updates through the multi-transport messaging system.

## Core Architecture

### 1. Integration Model
- **Syft-serve based**: Watcher will use syft-serve to create persistent server endpoints
- **Process isolation**: Runs as separate server process that outlasts the Python session
- **Lifecycle**: Independent of client instance - persists until explicitly stopped
- **API**: Exposed through `client._watcher_manager` property and related methods
- **Server naming**: `watcher_sender_{email}` format for unique identification
- **HTTP endpoints**: Status, control, and monitoring via HTTP API

### 2. Component Structure

```
syft_client/
├── sync/
│   ├── watcher/
│   │   ├── __init__.py
│   │   ├── file_watcher.py      # Main watcher server endpoint creation
│   │   ├── watcher_manager.py   # Client-side watcher management
│   │   ├── sync_history.py      # Echo prevention and history tracking
│   │   ├── event_handler.py     # File system event processing
│   │   └── bidirectional.py     # Inbox polling for two-way sync
│   └── ...existing sync modules...
```

## Key Features

### 1. File System Monitoring

**Watch Scope**:
- Default: `SyftBox/datasites/{user_email}/`
- Configurable paths within SyftBox
- Recursive monitoring with exclude patterns

**Event Types**:
- File created
- File modified  
- File deleted
- Directory changes (optional)

**Filtering**:
- Ignore hidden files/directories (starting with .)
- Skip temporary files (.tmp, .swp, ~, .DS_Store)
- User-defined exclude patterns
- Size limits (e.g., skip files >100MB)

### 2. Echo Prevention System

**Sync History Storage**:
```
SyftBox/
└── .syft_sync/
    └── history/
        └── {file_hash}/
            ├── metadata.json     # Sync metadata
            └── {message_id}.json # Individual sync records
```

**Metadata Structure**:
```json
{
  "file_path": "datasites/user@email.com/data.csv",
  "file_hash": "sha256:abc123...",
  "last_sync": {
    "message_id": "msg_20250927_123456_abc123",
    "timestamp": 1234567890.123,
    "peer": "friend@example.com",
    "transport": "gsheets",
    "direction": "received"  // or "sent"
  },
  "sync_history": [
    {
      "message_id": "msg_20250927_123456_abc123",
      "timestamp": 1234567890.123,
      "peer": "friend@example.com",
      "transport": "gsheets",
      "direction": "received",
      "file_size": 1024
    }
  ]
}
```

**Echo Detection Logic**:
1. File change detected
2. Compute file hash
3. Check sync history
4. If hash matches recent sync (within threshold):
   - Skip (it's an echo)
5. If hash differs or no recent sync:
   - Process the change
6. Update sync history after sending

### 3. Smart Send Logic

**Transport Selection**:
- Leverage existing transport negotiator
- Allow per-pattern transport preferences
- Example: `*.csv` → gsheets, `*.zip` → gdrive_files

**Batching**:
- Queue rapid changes (e.g., multiple saves)
- Send after quiet period (configurable delay)
- Combine multiple small files into one message

**Error Handling**:
- Retry failed sends with exponential backoff
- Queue messages during offline periods
- Report persistent failures to user

### 4. Bidirectional Sync

**Inbox Polling**:
- Periodic `check_inbox()` for all peers
- Configurable interval (default: 30 seconds)
- Smart polling: increase frequency after recent activity

**Conflict Resolution**:
- Last-write-wins by default
- Optional: create conflict copies
- Future: three-way merge for text files

### 5. Configuration

**Settings Structure**:
```python
watcher_config = {
    "enabled": True,
    "paths": ["datasites/{user_email}"],  # Paths to watch
    "exclude_patterns": ["*.tmp", ".*", "__pycache__"],
    "echo_threshold": 60,  # seconds
    "batch_delay": 2,  # seconds to wait for more changes
    "check_inbox_interval": 30,  # seconds
    "max_file_size": 100 * 1024 * 1024,  # 100MB
    "transport_rules": {
        "*.csv": "gsheets",
        "*.txt": "gsheets",
        "*": "auto"  # Use negotiator
    },
    "peer_filters": {
        "include": [],  # If set, only sync with these peers
        "exclude": []   # Never sync with these peers
    }
}
```

## API Design

### Starting the Watcher

```python
# Simple start - creates persistent syft-serve endpoint
watcher = client.start_watcher()

# With configuration
watcher = client.start_watcher(
    paths=["datasites/user@email.com/projects"],
    exclude_patterns=["*.log", "temp/*"],
    bidirectional=True,
    check_interval=60
)

# Check if watcher already running (survives Python restarts)
if client._watcher_manager.is_running():
    print("Watcher already active from previous session")
```

### Watcher Control

```python
# Status - queries the syft-serve endpoint
status = client._watcher_manager.status()
# Returns: {
#   "running": True,
#   "server_url": "http://localhost:8080",
#   "server_name": "watcher_sender_user_at_email_com",
#   "files_watched": 42,
#   "sent_count": 10,
#   "received_count": 5,
#   "error_count": 0,
#   "last_activity": "2025-09-27T12:34:56"
# }

# Stop the persistent watcher
client._watcher_manager.stop()

# List all active watchers (across all emails)
active_watchers = client._watcher_manager.list_all()

# Get history
history = client._watcher_manager.get_history(
    file_path="data.csv",
    limit=10
)
```

### Event Callbacks

```python
# Note: Callbacks are configured when starting the watcher since it runs in a separate process
client.start_watcher(
    on_send=lambda file, peer: print(f"Sent {file} to {peer}"),
    on_receive=lambda file, peer: print(f"Received {file} from {peer}"),
    on_error=lambda error: print(f"Error: {error}")
)
```

## Implementation Phases

### Phase 1: Basic Watcher
- File system monitoring
- Send-only (no bidirectional)
- Basic echo prevention
- Manual start/stop

### Phase 2: Bidirectional Sync
- Inbox polling
- Conflict detection
- Improved echo prevention
- Configuration system

### Phase 3: Advanced Features
- Smart transport selection rules
- Batching and optimization
- Event callbacks
- Performance monitoring

### Phase 4: Future Enhancements
- Real-time sync via webhooks
- Selective sync UI
- Sync status dashboard
- Mobile app integration

## Performance Considerations

### Resource Usage
- Separate syft-serve process for isolation
- Persistent across Python sessions
- Minimal memory footprint per watcher
- Efficient file hashing (chunk-based)

### Scalability
- Handle thousands of files
- Multiple peers without degradation
- Rate limiting for API calls
- Backpressure handling

### Reliability
- Process isolation prevents crashes affecting main client
- Automatic restart capability
- State persistence across sessions
- Network failure handling with retry logic

## Security Considerations

- Only sync files within SyftBox
- Respect peer permissions
- No automatic execution of received files
- Audit trail of all sync activity

## Testing Strategy

### Unit Tests
- Event handler logic
- Echo prevention algorithm
- Sync history management
- Configuration validation

### Integration Tests
- Full sync flow
- Multi-peer scenarios
- Conflict resolution
- Error recovery

### Performance Tests
- Large file handling
- Many small files
- High change frequency
- Network interruptions

## Migration Path

For users of the current file_watcher.py:
1. Provide compatibility mode
2. Import existing settings
3. Migrate sync history
4. Gradual feature adoption

## Success Metrics

- Files synced successfully: >99%
- Echo prevention accuracy: >99.9%
- Resource usage: <50MB RAM, <1% CPU
- User satisfaction: Minimal manual intervention
- Sync latency: <5 seconds for small files

## Open Questions

1. Should we support sync outside SyftBox directory?
2. How to handle symbolic links?
3. Should deleted files go to trash or permanent delete?
4. Real-time sync via Gmail push notifications?
5. Integration with version control systems?
6. How to handle multiple watchers for the same email?
7. Should watchers auto-start on system boot?
8. How to manage syft-serve dependencies and updates?