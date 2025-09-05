# Sync Echo Prevention

The syft-client includes sync echo prevention to avoid infinite loops where the same file gets synced back and forth between peers.

## How it works

When the file watcher detects a change, it checks if the file's content matches the **most recent sync** (stored in `.sync_history`). If it does, the change is considered an "echo" and is not propagated. If the file has been edited since the most recent sync, it will be sent even if there are older syncs with matching content.

### The Logic

1. When a file changes, the watcher computes its hash
2. It finds the **most recent sync** for that file (by timestamp in the folder name)
3. If the most recent sync is within the threshold (default 60 seconds) AND matches the current content → it's an echo
4. If the most recent sync doesn't match → the file has been edited and should be sent

This ensures that:
- Real edits are always detected and sent
- Echo prevention only applies to the most recent sync
- Older syncs are irrelevant - only the latest state matters

## Configuration Options

### Environment Variables

#### `SYFT_SYNC_ECHO_THRESHOLD`
- **Default**: 60 (seconds)
- **Description**: How recent the most recent sync must be to be considered for echo prevention
- **Example**: `export SYFT_SYNC_ECHO_THRESHOLD=120` (2 minutes)
- **Set to 0**: Disables echo prevention entirely

### Python API

When using the client programmatically:

```python
import syft_client as sc

client = sc.login("user@example.com")

# Check if a file matches the most recent sync (default: 60 seconds)
is_echo = client._is_file_from_recent_sync("/path/to/file.txt")

# Custom threshold
is_echo = client._is_file_from_recent_sync("/path/to/file.txt", threshold_seconds=120)

# Get info about the most recent sync
sync_info = client._get_recent_sync_info("/path/to/file.txt")
if sync_info:
    print(f"Most recent sync was {sync_info['age_seconds']}s ago")
```

## Sync History Storage

Sync history is stored in `.sync_history` directories within each datasite folder:
```
datasites/
└── user@example.com/
    └── project/
        ├── file.txt
        └── .sync_history/
            └── file.txt/
                ├── 1234567890.0_abc123.syftmessage/  ← Most recent
                └── 1234567891.0_def456.syftmessage/  ← Older
```

The folder names contain timestamps, allowing the system to identify the most recent sync.

## Cleaning Sync History

To save disk space, you can clean old sync history:

```python
# Clean history for a specific datasite (keeps most recent sync)
client._clean_sync_history_for_datasite(datasite_path)

# Remove all history
client._clean_sync_history_for_datasite(datasite_path, keep_latest=False)
```

## Troubleshooting

If files are not syncing:
1. Check if echo prevention is too aggressive: increase `SYFT_SYNC_ECHO_THRESHOLD`
2. Look at the most recent sync in `.sync_history` to see what content is expected
3. Disable temporarily: set `SYFT_SYNC_ECHO_THRESHOLD=0`

If you're getting sync loops:
1. Ensure echo prevention is enabled (it is by default)
2. Check that all peers have the updated syft-client with echo prevention
3. Verify the sync history is being written correctly