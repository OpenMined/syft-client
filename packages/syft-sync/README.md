# Syft Sync

A bidirectional file synchronization system with append-only logging, designed for distributed data science workflows with PySyft.

## Features

- **Bidirectional Sync**: Watch source files and sync to destination via append-only log
- **Append-Only Logging**: Never lose file history - every change is preserved
- **Syft Integration**: Creates SyftMessage archives for all file changes
- **Log-Based Sync**: Receiver watches log and recreates files at destination
- **Duplicate Detection**: Smart content-based deduplication prevents redundant logging
- **Version History**: Complete timeline of all file changes with easy restoration
- **Interactive Explorer**: Browse and restore any version of any file
- **High Performance**: Handles thousands of file operations per second
- **Crash Recovery**: Resilient to system failures with automatic recovery
- **Extensible Architecture**: Easy to add new watcher types and storage backends

## Installation

```bash
pip install syft-sync
```

For development:
```bash
git clone https://github.com/OpenMined/syft-sync.git
cd syft-sync
pip install -e .[dev]
```

## Quick Start

```python
from syft_sync import AppendOnlyLogWatcher

# Create a watcher for a directory
watcher = AppendOnlyLogWatcher(
    watch_path="./my_project",
    log_path="./my_project_log",
    verbose=True
)

# Start watching
watcher.start()

# ... make some file changes ...

# Stop watching
watcher.stop()

# Explore the log
watcher.explore_log()
```

## Usage Examples

### Basic File Watching

```python
from syft_sync import AppendOnlyLogWatcher

# Watch a directory and log all changes
with AppendOnlyLogWatcher("./data", verbose=True) as watcher:
    # Make changes to files in ./data
    # All changes are automatically logged
    pass

# Get file history
history = watcher.get_file_history("./data/important.txt")
for version in history:
    print(f"Version: {version['version_id']}")
    print(f"Time: {version['timestamp']}")
    print(f"Event: {version['event_type']}")
```

### Custom Event Handlers

```python
from syft_watcher import BaseWatcher, EventHandler, FileEvent

class MyEventHandler(EventHandler):
    def on_file_created(self, event: FileEvent):
        print(f"New file created: {event.src_path}")
    
    def on_file_modified(self, event: FileEvent):
        print(f"File modified: {event.src_path}")
        # Add custom logic here

watcher = AppendOnlyLogWatcher(
    watch_path="./data",
    event_handler=MyEventHandler()
)
```

### Restoring File Versions

```python
# Get all versions of a file
history = watcher.get_file_history("./data/config.json")

# Restore a specific version
version_id = history[0]['version_id']
watcher.restore_version(
    file_path="./data/config.json",
    version_id=version_id,
    restore_path="./data/config.restored.json"
)
```

### Bidirectional Synchronization

Syft Sync provides receiver components to sync files from a log:

```python
from syft_sync import SyftAppendOnlyLogWatcher, SyftLogReceiver

# Watch source directory
watcher = SyftAppendOnlyLogWatcher(
    watch_path="./source_files",
    log_path="./sync_log",
    verbose=True
)

# Sync from log to destination
receiver = SyftLogReceiver(
    log_path="./sync_log",
    output_path="./destination_files",
    verbose=True,
    sync_mode="latest"  # or "all_versions"
)

# Start both
watcher.start()
receiver.start()

# Files created/modified in source will be synced to destination
# The sync happens through the append-only log
```

### Interactive Log Explorer

```python
# Launch interactive explorer
watcher.explore_log()

# Or use the standalone explorer
from syft_sync.utils import LogExplorer
from syft_sync.storage import LogStorage

storage = LogStorage("./my_project_log")
explorer = LogExplorer(storage)
explorer.run()
```

### Syft Integration

Create SyftMessage archives for all file changes:

```python
from syft_watcher import SyftAppendOnlyLogWatcher

# Create Syft-integrated watcher
watcher = SyftAppendOnlyLogWatcher("./data", verbose=True)

with watcher:
    # All file changes create SyftMessage archives
    pass

# Get SyftMessages for a file
messages = watcher.get_all_syft_messages("./data/file.txt")

# Export SyftMessage archive
watcher.export_syft_archive(version_id, "./archive.syft")

# Import SyftMessage archive
watcher.import_syft_archive("./archive.syft")

# Restore from SyftMessage
watcher.restore_from_syft(version_id, "./restored_file.txt")
```

## Architecture

Syft Watcher is built with a modular architecture:

- **Core**: Base classes and event definitions
- **Watchers**: Different watcher implementations (append-only, etc.)
- **Storage**: Backend storage systems for logs
- **Utils**: Utilities for exploring and formatting data

## Advanced Features

### Duplicate Detection

The watcher automatically detects and skips duplicate file saves using content-based hashing:

```python
# These operations will only create one log entry
with open("file.txt", "w") as f:
    f.write("Hello")

# No change - skipped
with open("file.txt", "w") as f:
    f.write("Hello")

# Change detected - logged
with open("file.txt", "w") as f:
    f.write("Hello World")
```

### Exclude Patterns

Customize which files to ignore:

```python
watcher = AppendOnlyLogWatcher(
    watch_path="./project",
    exclude_patterns=['*.tmp', '*.log', '.git', 'node_modules']
)
```

### Statistics

Get detailed statistics about the watcher:

```python
stats = watcher.get_stats()
print(f"Files created: {stats['files_created']}")
print(f"Files modified: {stats['files_modified']}")
print(f"Runtime: {stats['runtime']}")
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=syft_watcher

# Run specific test file
pytest tests/test_append_only.py
```

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Roadmap

- [ ] S3 storage backend
- [ ] Real-time synchronization
- [ ] Compression support
- [ ] Encryption at rest
- [ ] Web UI for log exploration
- [ ] Integration with PySyft

## Support

- **Issues**: [GitHub Issues](https://github.com/OpenMined/syft-watcher/issues)
- **Discussions**: [GitHub Discussions](https://github.com/OpenMined/syft-watcher/discussions)
- **Documentation**: [Full Documentation](https://github.com/OpenMined/syft-watcher/wiki)