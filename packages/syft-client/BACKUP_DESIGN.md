# SyftClient Backup System Design

## Overview
Pure Python implementation to backup `~/.syft` to a designated transport (e.g., Google Drive) using API-based sync with smart change detection.

## Architecture

### 1. BackupManager Class
```python
class BackupManager:
    def __init__(self, client: SyftClient, transport_name: str = "gdrive_files"):
        self.client = client
        self.transport = self._get_transport(transport_name)
        self.local_syft = Path.home() / ".syft"
        self.remote_backup_path = "SyftBox/.syft_backup"
        self.manifest_path = self.local_syft / ".backup_manifest.json"
        self.manifest = self._load_manifest()
```

### 2. Change Detection Strategy
- Use file checksums (SHA-256) to detect changes
- Store manifest with: `{file_path: {checksum, mtime, size}}`
- Only sync files where checksum differs from manifest

### 3. Sync Operations

#### Initial Sync
```python
def initial_sync(self):
    """First-time backup of entire ~/.syft"""
    for file_path in self.local_syft.rglob("*"):
        if file_path.is_file() and not self._should_ignore(file_path):
            self._backup_file(file_path)
    self._save_manifest()
```

#### Incremental Sync
```python
def sync(self):
    """Sync only changed files"""
    changes = self._detect_changes()
    for change in changes:
        if change.type == "modified":
            self._backup_file(change.path)
        elif change.type == "deleted":
            self._delete_remote(change.path)
        elif change.type == "new":
            self._backup_file(change.path)
    self._save_manifest()
```

### 4. Auto-Sync Implementation
```python
def enable_auto_backup(self, interval_seconds=300):
    """Enable periodic sync every N seconds"""
    def sync_loop():
        while self.enabled:
            self.sync()
            time.sleep(interval_seconds)
    
    thread = threading.Thread(target=sync_loop, daemon=True)
    thread.start()
```

### 5. File Organization
```
Google Drive:
SyftBox/
└── .syft_backup/
    ├── manifest.json          # Backup state
    ├── contacts/              # Mirror of ~/.syft/contacts
    │   ├── alice_at_gmail.json
    │   └── bob_at_gmail.json
    ├── discovery/             # Discovery cache
    ├── credentials/           # Encrypted OAuth tokens
    └── settings.json          # User settings
```

### 6. Ignored Files
- Temporary files (`*.tmp`, `*.swp`)
- Lock files (`*.lock`)
- Large cache files (>10MB)
- `.DS_Store`, `Thumbs.db`

### 7. Error Handling
- Retry failed uploads (3 attempts with exponential backoff)
- Queue failed files for next sync
- Log errors to `~/.syft/backup_errors.log`

### 8. Restore Functionality
```python
def restore(self, backup_date: Optional[str] = None):
    """Restore from backup"""
    # 1. List available backups
    # 2. Download manifest
    # 3. Compare with local state
    # 4. Download changed/missing files
    # 5. Verify checksums
```

### 9. User Interface
```python
# Enable backup
client.backup.enable(transport="gdrive_files")

# Manual sync
client.backup.sync()

# Check status
client.backup.status()
# Output: Last sync: 2 mins ago, Files: 42, Size: 2.3MB

# Restore
client.backup.restore()

# Disable
client.backup.disable()
```

### 10. Performance Optimizations
- Batch API calls (upload multiple small files together)
- Compress JSON files before upload
- Use multiprocessing for parallel uploads
- Cache remote file listings

### 11. Security Considerations
- Encrypt sensitive files (credentials, keys) before upload
- Use transport's native encryption if available
- Never backup raw OAuth tokens

### 12. Implementation Priority
1. **Phase 1**: Manual sync command
2. **Phase 2**: Auto-sync with change detection  
3. **Phase 3**: Restore functionality
4. **Phase 4**: Multi-device conflict resolution

## Code Structure
```
syft_client/
└── backup/
    ├── __init__.py
    ├── manager.py      # Main BackupManager class
    ├── sync.py         # Sync logic and change detection
    ├── manifest.py     # Manifest handling
    └── restore.py      # Restore functionality
```