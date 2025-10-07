# Receiver Design for syft-client

## Overview
The receiver provides automatic inbox monitoring and message processing for syft-client, complementing the file watcher to create a complete bidirectional sync system. It continuously polls peer inboxes for new messages and processes them automatically.

## Core Architecture

### 1. Integration Model
- **Syft-serve based**: Uses syft-serve to create persistent server endpoints
- **Process isolation**: Runs as separate server process that outlasts the Python session
- **Lifecycle**: Independent of client instance - persists until explicitly stopped
- **API**: Exposed through `client._receiver_manager` property and related methods
- **Server naming**: `receiver_{email}` format for unique identification

### 2. Component Structure

```
syft_client/
├── sync/
│   ├── receiver/
│   │   ├── __init__.py
│   │   ├── receiver.py          # Main receiver server endpoint creation
│   │   ├── receiver_manager.py  # Client-side receiver management
│   │   ├── inbox_monitor.py     # Inbox polling and change detection
│   │   └── message_processor.py # Message processing and merging
│   └── ...existing sync modules...
```

## Key Features

### 1. Inbox Monitoring

**Polling Strategy**:
- Default interval: 30 seconds (configurable)
- Smart polling: Increase frequency after recent activity
- Batch checking: Check all peers in one cycle
- Resource-efficient: Only process when changes detected

**Change Detection**:
- Track last check timestamp per peer/transport
- Use message counts for quick change detection
- Compare message IDs to identify new messages
- Skip already processed messages

### 2. Message Processing Pipeline

```
1. Detect new messages → 2. Download → 3. Extract → 4. Apply → 5. Archive
```

**Processing Steps**:
1. **Detection**: Poll all peer inboxes for new messages
2. **Download**: Retrieve message archives from transports
3. **Extraction**: Unpack files to designated locations
4. **Application**: Merge changes into SyftBox directory
5. **Archiving**: Move processed messages to archive

### 3. Multi-Transport Support

**Transport Coordination**:
- Check all active transports per peer
- Handle different message formats (tar.gz for Drive, direct for Sheets)
- Respect transport-specific rate limits
- Fallback to alternative transports on failure

**Priority Order**:
1. Gmail (for critical/small messages)
2. Google Sheets (for structured data)
3. Google Drive (for large files)
4. Other transports as available

### 4. State Management

**Tracking Structure**:
```
~/.syft/receiver/
└── state/
    ├── {email}/
    │   ├── last_check.json      # Last check timestamps
    │   ├── processed_messages.json # Already processed message IDs
    │   └── peer_states.json     # Per-peer state tracking
    └── stats.json                # Global receiver statistics
```

**State Information**:
```json
{
  "peer_states": {
    "friend@example.com": {
      "last_check": "2024-01-01T12:00:00Z",
      "last_message_id": "msg_12345",
      "message_count": 42,
      "transports_checked": ["gdrive_files", "gsheets"]
    }
  },
  "stats": {
    "total_messages_processed": 1234,
    "last_error": null,
    "uptime_seconds": 3600
  }
}
```

### 5. Error Handling

**Retry Logic**:
- Exponential backoff for transport errors
- Skip problematic messages after N attempts
- Continue processing other peers on individual failures
- Log errors for debugging

**Recovery**:
- Persist state between restarts
- Resume from last known state
- Re-process incomplete downloads
- Clean up partial extractions

## API Design

### Starting the Receiver

```python
# Simple start
receiver = client.start_receiver()

# With configuration
receiver = client.start_receiver(
    check_interval=30,           # Seconds between inbox checks
    process_immediately=True,    # Process existing messages on start
    transports=["gdrive_files", "gsheets"],  # Specific transports to monitor
    auto_accept=True            # Auto-accept peer requests
)

# Check if receiver already running
if client._receiver_manager.is_running():
    print("Receiver already active from previous session")
```

### Receiver Control

```python
# Status
status = client._receiver_manager.status()
# Returns: {
#   "running": True,
#   "server_url": "http://localhost:8002",
#   "server_name": "receiver_demo_at_example_com",
#   "messages_processed": 42,
#   "last_check": "2024-01-01T12:00:00Z",
#   "peers_monitored": 5,
#   "error_count": 0
# }

# Stop the receiver
client._receiver_manager.stop()

# Get detailed statistics
stats = client._receiver_manager.get_stats()

# Force immediate check (useful for testing)
client._receiver_manager.check_now()
```

### Event Callbacks

```python
# Register callbacks when starting
client.start_receiver(
    on_message=lambda msg, peer: print(f"Received {msg} from {peer}"),
    on_error=lambda error: print(f"Error: {error}"),
    on_complete=lambda count: print(f"Processed {count} messages")
)
```

## Implementation Strategy

### Phase 1: Basic Receiver
```python
def receiver_main():
    """Main receiver loop"""
    while running:
        # For each peer
        for peer in client.peers:
            try:
                # Check inbox using existing method
                messages = peer.check_inbox(
                    download_dir=inbox_dir,
                    verbose=False
                )
                
                # Process any new messages
                if messages:
                    process_messages(messages, peer)
                    
            except Exception as e:
                log_error(e)
        
        # Wait for next check
        time.sleep(check_interval)
```

### Phase 2: Smart Change Detection
```python
def check_peer_inbox(peer, last_state):
    """Check with change detection"""
    # Quick check for changes
    has_changes = False
    
    for transport in peer.get_active_transports():
        # Get message count or latest ID
        current_state = transport.get_inbox_state()
        
        if current_state != last_state.get(transport.name):
            has_changes = True
            break
    
    # Only download if changes detected
    if has_changes:
        return peer.check_inbox()
    
    return None
```

### Phase 3: Parallel Processing
```python
def check_all_inboxes():
    """Check all peers in parallel"""
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = []
        
        for peer in client.peers:
            future = executor.submit(check_peer_inbox, peer)
            futures.append((peer, future))
        
        # Collect results
        for peer, future in futures:
            try:
                messages = future.result(timeout=30)
                if messages:
                    process_messages(messages, peer)
            except Exception as e:
                log_error(f"Error checking {peer.email}: {e}")
```

## Configuration

### Environment Variables
```bash
SYFT_RECEIVER_INTERVAL=30        # Check interval in seconds
SYFT_RECEIVER_BATCH_SIZE=10      # Max peers to check in parallel
SYFT_RECEIVER_TIMEOUT=300        # Timeout for individual checks
SYFT_RECEIVER_AUTO_ACCEPT=true   # Auto-accept peer requests
SYFT_RECEIVER_MAX_RETRIES=3      # Max retries for failed downloads
```

### Configuration File
```python
receiver_config = {
    "enabled": True,
    "check_interval": 30,
    "transports": ["gdrive_files", "gsheets", "gmail"],
    "auto_accept_requests": True,
    "download_dir": "~/SyftBox/inbox",
    "archive_processed": True,
    "max_message_size": 100 * 1024 * 1024,  # 100MB
    "parallel_downloads": 3,
    "state_dir": "~/.syft/receiver/state"
}
```

## Interaction with Watcher

### Coordinated Operation
1. **Watcher** detects local changes → sends to peers
2. **Receiver** detects inbox changes → downloads from peers
3. Both use sync history to prevent loops

### Echo Prevention
- Receiver marks downloaded files with metadata
- Watcher checks metadata before sending
- Shared sync history between components
- Time-based threshold for recent syncs

## Performance Considerations

### Resource Usage
- Single thread for monitoring
- Thread pool for parallel downloads
- Minimal memory footprint
- Efficient state persistence

### Scalability
- Handle hundreds of peers
- Batch API calls where possible
- Progressive backoff for rate limits
- Prioritize active peers

## Security Considerations

- Validate message signatures
- Sandbox extraction process
- Verify sender identity
- Audit trail of all downloads
- No automatic code execution

## Testing Strategy

### Unit Tests
- Inbox polling logic
- Change detection algorithm
- Message processing pipeline
- State management

### Integration Tests
- Full receive flow
- Multi-peer scenarios
- Transport failures
- Recovery from crashes

### Performance Tests
- High message volume
- Many peers
- Large file handling
- Network interruptions

## Success Metrics

- Messages processed: >99% success rate
- Detection latency: <check_interval + 5s
- Resource usage: <100MB RAM, <1% CPU idle
- Recovery time: <60s after crash

## Future Enhancements

1. **Push Notifications**: Use webhooks where available
2. **Selective Sync**: Filter messages by pattern/size
3. **Compression**: Compress state files
4. **Analytics**: Detailed sync statistics dashboard
5. **Smart Scheduling**: Adaptive polling based on peer activity

## Implementation Timeline

### Week 1: Basic Receiver
- Server endpoint creation
- Simple polling loop
- Basic message processing

### Week 2: State Management
- Change detection
- State persistence
- Error handling

### Week 3: Advanced Features
- Parallel processing
- Transport coordination
- Performance optimization

### Week 4: Integration
- Watcher coordination
- Echo prevention
- Testing and documentation