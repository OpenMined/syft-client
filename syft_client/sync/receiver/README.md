# SyftClient Inbox Receiver

The inbox receiver provides automatic monitoring and processing of messages from peers, complementing the file watcher to create a complete bidirectional sync system.

## Features

- **Automatic inbox monitoring**: Checks all peer inboxes at regular intervals
- **Smart change detection**: Only processes new messages
- **Message processing**: Downloads, extracts, and places files automatically
- **Peer request handling**: Auto-accepts new peer requests (configurable)
- **Persistent process**: Runs via syft-serve, survives Python restarts
- **State management**: Tracks processed messages to avoid duplicates

## Quick Start

```python
import syft_client as sc

# Login
client = sc.login("your_email@gmail.com")

# Start the receiver
client.start_receiver()

# Check status
client._receiver_manager.status()

# Stop the receiver
client._receiver_manager.stop()
```

## How It Works

1. **Polling Loop**: Checks each peer's inbox every 30 seconds (configurable)
2. **Change Detection**: Tracks message IDs and content hashes
3. **Download**: Uses `peer.check_inbox()` to download new messages
4. **Processing**: Extracts archives and places files in correct locations
5. **State Tracking**: Records processed messages to avoid re-processing

## Full Bidirectional Sync

For complete synchronization, run both watcher and receiver:

```python
# Start both services
client.start_watcher()   # Local changes → peers
client.start_receiver()  # Peer changes → local

print("✓ Full bidirectional sync enabled!")
```

## Directory Structure

```
SyftBox/
├── inbox/                    # Downloaded messages (temporary)
├── datasites/
│   └── peer@example.com/    # Files from peers
└── .syft_archive/           # Processed message archives
    └── peer@example.com/    # Archived messages
```

## Configuration

```python
# Start with custom settings
client.start_receiver(
    check_interval=60,        # Check every minute
    process_immediately=True, # Process existing messages
    auto_accept=True,        # Accept peer requests
    verbose=True             # Show status messages
)
```

Environment variables:

- `SYFT_RECEIVER_INTERVAL`: Default check interval (seconds)
- `SYFT_RECEIVER_AUTO_ACCEPT`: Auto-accept peer requests

## State Management

The receiver maintains state in `~/.syft/receiver/state/`:

- `peer_states.json`: Last check times and content hashes
- `processed_messages.json`: Already processed message IDs

## Architecture

- **ReceiverManager**: Client-side API and control
- **InboxMonitor**: Change detection and state tracking
- **MessageProcessor**: File extraction and placement
- **receiver.py**: syft-serve endpoint implementation

## Comparison with Watcher

| Feature   | Watcher         | Receiver           |
| --------- | --------------- | ------------------ |
| Direction | Outbound (send) | Inbound (receive)  |
| Monitors  | File system     | Peer inboxes       |
| Trigger   | File changes    | New messages       |
| Action    | Send to peers   | Download & extract |

## Troubleshooting

1. **Receiver not detecting messages**:

   - Check if peers are configured: `list(client.peers)`
   - Verify peer has sent messages
   - Check logs in `~/.syft_logs/server_envs/receiver_*/`

2. **Messages not processing**:

   - Check inbox directory permissions
   - Verify sufficient disk space
   - Look for errors in receiver status

3. **State issues**:
   - Clear state: `rm -rf ~/.syft/receiver/state/`
   - Restart receiver to reprocess all messages
