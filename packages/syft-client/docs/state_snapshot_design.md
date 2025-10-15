# SyftBox State Snapshot System Design

## Overview

This document outlines a design for adding a state snapshot system to SyftBox that leverages Google Drive's free storage and bandwidth to create an efficient distributed filesystem with minimal storage costs.

## Motivation

Current limitations:
- Inbox/outbox folders accumulate messages over time, increasing storage costs
- No efficient way to query current state without processing all messages
- New peers must download and process entire message history
- No automatic cleanup of old messages

Proposed benefits:
- Leverage Google Drive's free 15GB storage and unlimited bandwidth
- Enable sparse loading of file state (only download what's needed)
- Automatic cleanup of old data to stay within free tier
- Faster sync for new peers
- Efficient state queries without processing message history

## Architecture

### Folder Structure

```
datasites/
  alice@example.com/
    inbox_outbox/                 # Existing: Message passing (auto-cleanup after X days)
    state/                        # New: State management
      current/                    # Latest state only
        manifest.json            # File tree with metadata
        indexes/                 # Query indexes
          by_date.json          # Files indexed by modification date
          by_type.json          # Files indexed by type/extension
          by_size.json          # Files indexed by size ranges
        chunks/                  # Content-addressed file storage
          ab/                    # First 2 chars of hash
            abcd1234...         # File content stored by hash
      snapshots/                 # Historical snapshots
        2024-01-15T12:00:00Z/   # ISO timestamp
          manifest.json         # State at this point in time
        2024-01-08T12:00:00Z/
          manifest.json
      config.json               # Snapshot configuration
```

### Manifest Format

```json
{
  "version": "1.0",
  "timestamp": "2024-01-15T12:00:00Z",
  "owner": "alice@example.com",
  "sequence_number": 12345,
  "parent_hash": "sha256:previous_manifest_hash",
  "vector_clock": {
    "alice@example.com": 12345,
    "bob@example.com": 6789
  },
  "files": {
    "path/to/file.txt": {
      "hash": "sha256:abcd1234...",
      "size": 1024,
      "modified": "2024-01-15T10:30:00Z",
      "permissions": "rw-r--r--",
      "chunks": ["hash1", "hash2"],  // For large files
      "encoding": "UTF-8",
      "normalized_name": "NFC"  // Unicode normalization
    }
  },
  "directories": {
    "path/to/": {
      "created": "2024-01-01T00:00:00Z",
      "permissions": "rwxr-xr-x"
    }
  },
  "stats": {
    "total_files": 150,
    "total_size": 52428800,
    "total_directories": 25,
    "checksum": "sha256:manifest_checksum"
  }
}
```

### State Update Protocol

1. **Message Processing**: Continue using inbox/outbox for real-time updates
2. **State Compilation**: Periodically compile messages into state updates
3. **Snapshot Creation**: Create snapshots based on time/size thresholds
4. **Garbage Collection**: Clean up old messages and snapshots

## Implementation Plan

### Phase 1: State Infrastructure

#### 1.1 Create State Manager (`syft_client/sync/state/`)

```python
# state_manager.py
import fcntl
import json
import time
from pathlib import Path
from typing import Dict, List, Optional

class StateManager:
    def __init__(self, client, peer_email):
        self.client = client
        self.peer_email = peer_email
        self.state_folder = f"state/"
        self.lock_manager = DistributedLockManager(client)
        self.vector_clock = VectorClock(client.email)
        
    def get_current_manifest(self) -> Dict:
        """Load current state manifest from Drive with retry logic"""
        for attempt in range(3):
            try:
                manifest = self._download_manifest("current/manifest.json")
                if self._validate_manifest(manifest):
                    return manifest
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        
    def update_manifest(self, changes: List[FileChange]):
        """Apply changes to manifest with distributed locking"""
        with self.lock_manager.acquire_lock(f"state/{self.peer_email}/manifest", timeout=30):
            # Load current manifest
            current = self.get_current_manifest()
            
            # Update vector clock
            self.vector_clock.increment()
            current["vector_clock"] = self.vector_clock.to_dict()
            
            # Apply changes
            new_manifest = self._apply_changes(current, changes)
            
            # Calculate checksum
            new_manifest["stats"]["checksum"] = self._calculate_checksum(new_manifest)
            
            # Atomic write with temp file
            self._atomic_write_manifest(new_manifest)
    
    def _atomic_write_manifest(self, manifest: Dict):
        """Write manifest atomically using temp file + rename"""
        temp_path = f"current/manifest.tmp.{time.time()}"
        final_path = "current/manifest.json"
        
        # Upload to temp location
        self._upload_json(temp_path, manifest)
        
        # Atomic rename (Drive supports this)
        self._rename_file(temp_path, final_path)
    
    def _validate_manifest(self, manifest: Dict) -> bool:
        """Validate manifest integrity"""
        # Check version compatibility
        if not self._check_version_compatibility(manifest["version"]):
            raise ValueError(f"Incompatible manifest version: {manifest['version']}")
            
        # Verify checksum
        expected = manifest["stats"]["checksum"]
        actual = self._calculate_checksum(manifest)
        
        return expected == actual
```

#### 1.2 Content-Addressed Storage

```python
# content_store.py
import hashlib
import time
from typing import Set, Dict, Optional, List
from collections import defaultdict

class ContentAddressedStore:
    def __init__(self, client):
        self.client = client
        self.chunk_registry = ChunkRegistry()  # Tracks chunk references
        self.upload_cache = {}  # In-flight uploads
        
    def store_file(self, content: bytes) -> str:
        """Store file content and return hash with deduplication"""
        # Use SHA-256 for strong collision resistance
        hash = hashlib.sha256(content).hexdigest()
        
        # Check if already uploading
        if hash in self.upload_cache:
            return self._wait_for_upload(hash)
        
        # Use full hash path to avoid collisions
        chunk_path = self._get_chunk_path(hash)
        
        # Check if already exists
        if self._chunk_exists(chunk_path):
            self.chunk_registry.add_reference(hash)
            return hash
            
        # Mark as uploading
        self.upload_cache[hash] = {"status": "uploading", "path": chunk_path}
        
        try:
            # Upload with verification
            self._upload_with_verification(chunk_path, content, hash)
            self.chunk_registry.add_reference(hash)
            self.upload_cache[hash]["status"] = "complete"
            return hash
        except Exception as e:
            del self.upload_cache[hash]
            raise
            
    def retrieve_file(self, hash: str, timeout: int = 30) -> bytes:
        """Retrieve file content by hash with retry logic"""
        chunk_path = self._get_chunk_path(hash)
        
        # Retry with exponential backoff for eventual consistency
        for attempt in range(5):
            try:
                content = self._download_chunk(chunk_path)
                # Verify hash matches
                actual_hash = hashlib.sha256(content).hexdigest()
                if actual_hash != hash:
                    raise ValueError(f"Hash mismatch: expected {hash}, got {actual_hash}")
                return content
            except FileNotFoundError:
                if attempt < 4:
                    time.sleep(2 ** attempt)
                else:
                    raise
                    
    def _get_chunk_path(self, hash: str) -> str:
        """Get chunk path using 3-level hierarchy to avoid collisions"""
        # Use 3 levels: aa/bb/cc/remaining_hash
        return f"chunks/{hash[:2]}/{hash[2:4]}/{hash[4:6]}/{hash[6:]}"
        
    def garbage_collect(self, active_manifests: List[Dict]) -> int:
        """Remove unreferenced chunks with safety checks"""
        # Build set of all referenced hashes
        referenced_hashes = set()
        for manifest in active_manifests:
            referenced_hashes.update(self._extract_hashes_from_manifest(manifest))
            
        # Find orphaned chunks with grace period
        orphaned = self.chunk_registry.find_orphaned(
            referenced_hashes, 
            grace_period_hours=24  # Keep orphans for 24h
        )
        
        # Delete in batches to avoid rate limits
        deleted = 0
        for batch in self._batch(orphaned, 100):
            deleted += self._delete_chunks(batch)
            time.sleep(1)  # Rate limit
            
        return deleted
```

#### 1.3 Distributed Locking

```python
# distributed_lock.py
class DistributedLockManager:
    """Google Drive-based distributed locking using lock files"""
    
    def __init__(self, client):
        self.client = client
        self.held_locks = {}
        
    @contextmanager
    def acquire_lock(self, resource: str, timeout: int = 30):
        """Acquire distributed lock with timeout"""
        lock_path = f".locks/{resource}.lock"
        lock_id = f"{self.client.email}_{time.time()}"
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Try to create lock file
                lock_data = {
                    "owner": self.client.email,
                    "id": lock_id,
                    "acquired": time.time(),
                    "expires": time.time() + timeout
                }
                
                # Use Drive's createIfNotExists flag
                if self._create_lock_file(lock_path, lock_data):
                    self.held_locks[resource] = lock_id
                    try:
                        yield
                        return
                    finally:
                        # Release lock
                        self._delete_lock_file(lock_path, lock_id)
                        del self.held_locks[resource]
                else:
                    # Check if existing lock is expired
                    existing = self._read_lock_file(lock_path)
                    if existing and existing["expires"] < time.time():
                        # Remove stale lock
                        self._delete_lock_file(lock_path, existing["id"])
                    else:
                        time.sleep(1)
            except Exception:
                time.sleep(1)
                
        raise TimeoutError(f"Failed to acquire lock for {resource}")
```

### Phase 2: State Synchronization

#### 2.1 Modify Message Processing

```python
# message_state_bridge.py
class MessageStateBridge:
    """Bridge between message system and state system to prevent loops"""
    
    def __init__(self, state_manager, sync_history):
        self.state_manager = state_manager
        self.sync_history = sync_history
        self.processing_queue = set()  # Messages currently being processed
        
    def process_message_with_state_update(self, message):
        """Process message and update state without causing echo"""
        message_id = message.message_id
        
        # Prevent reprocessing
        if message_id in self.processing_queue:
            return
            
        self.processing_queue.add(message_id)
        try:
            # Record in sync history FIRST to prevent echo
            self.sync_history.record_batch([
                {
                    "path": change.path,
                    "message_id": message_id,
                    "peer": message.sender_email,
                    "transport": message.transport,
                    "direction": "received"
                }
                for change in message.get_changes()
            ])
            
            # Process filesystem changes
            self._apply_filesystem_changes(message)
            
            # Update state manifest (but don't trigger watchers)
            with self.sync_history.suppress_echo():
                self.state_manager.update_manifest(message.get_changes())
                
        finally:
            self.processing_queue.remove(message_id)
```

#### 2.2 State Conflict Resolution

```python
# conflict_resolver.py
from typing import Dict, List, Tuple

class ConflictResolver:
    """Resolve conflicts between different state versions"""
    
    def __init__(self):
        self.resolution_strategies = {
            "last-write-wins": self._last_write_wins,
            "vector-clock": self._vector_clock_resolution,
            "three-way-merge": self._three_way_merge
        }
        
    def detect_conflicts(self, local_manifest: Dict, remote_manifest: Dict) -> List[str]:
        """Detect files with conflicts between manifests"""
        conflicts = []
        
        # Check vector clocks for causality
        local_vc = VectorClock.from_dict(local_manifest["vector_clock"])
        remote_vc = VectorClock.from_dict(remote_manifest["vector_clock"])
        
        if not (local_vc.happens_before(remote_vc) or remote_vc.happens_before(local_vc)):
            # Concurrent modifications - check individual files
            for path in set(local_manifest["files"]) & set(remote_manifest["files"]):
                local_file = local_manifest["files"][path]
                remote_file = remote_manifest["files"][path]
                
                if (local_file["hash"] != remote_file["hash"] and
                    local_file["modified"] != remote_file["modified"]):
                    conflicts.append(path)
                    
        return conflicts
        
    def resolve_conflicts(self, conflicts: List[str], strategy: str = "vector-clock") -> Dict:
        """Resolve conflicts using specified strategy"""
        resolver = self.resolution_strategies.get(strategy)
        if not resolver:
            raise ValueError(f"Unknown resolution strategy: {strategy}")
            
        resolutions = {}
        for conflict in conflicts:
            resolutions[conflict] = resolver(conflict)
            
        return resolutions

# state_sync.py
class StateSynchronizer:
    def __init__(self, client):
        self.client = client
        self.conflict_resolver = ConflictResolver()
        self.content_store = ContentAddressedStore(client)
        self.sync_locks = {}  # Prevent concurrent syncs
        
    def sync_path(self, path: str, peer_email: str):
        """Sync specific path with conflict detection"""
        # Prevent concurrent sync of same path
        lock_key = f"{peer_email}:{path}"
        if lock_key in self.sync_locks:
            return  # Already syncing
            
        self.sync_locks[lock_key] = True
        try:
            local_manifest = self.state_manager.get_current_manifest()
            remote_manifest = self.get_peer_manifest(peer_email)
            
            # Check for conflicts
            if path in local_manifest["files"] and path in remote_manifest["files"]:
                conflicts = self.conflict_resolver.detect_conflicts(
                    {"files": {path: local_manifest["files"][path]}},
                    {"files": {path: remote_manifest["files"][path]}}
                )
                
                if conflicts:
                    resolution = self.conflict_resolver.resolve_conflicts(conflicts)
                    # Apply resolution...
                    
            # Sync file if needed
            if path in remote_manifest["files"]:
                file_info = remote_manifest["files"][path]
                content = self.content_store.retrieve_file(file_info["hash"])
                self._write_with_normalization(path, content, file_info)
        finally:
            del self.sync_locks[lock_key]
    
    def _write_with_normalization(self, path: str, content: bytes, file_info: Dict):
        """Write file with proper Unicode normalization"""
        import unicodedata
        
        # Normalize path to NFC
        normalized_path = unicodedata.normalize('NFC', path)
        
        # Handle encoding
        if file_info.get("encoding") == "UTF-8":
            # Verify valid UTF-8
            try:
                content.decode('utf-8')
            except UnicodeDecodeError:
                # Log warning about encoding issue
                pass
                
        self.write_local_file(normalized_path, content)
```

### Phase 3: Automatic Cleanup

#### 3.1 Cleanup Configuration

```json
{
  "cleanup": {
    "inbox_retention_days": 7,
    "snapshot_retention_count": 4,
    "snapshot_interval_hours": 24,
    "max_storage_mb": 1024,
    "cleanup_interval_hours": 6,
    "rate_limit": {
      "operations_per_minute": 600,
      "backoff_multiplier": 2
    },
    "safety": {
      "min_snapshot_age_hours": 24,
      "chunk_grace_period_hours": 48,
      "dry_run": false
    }
  }
}
```

#### 3.2 Safe Cleanup Implementation

```python
# cleanup_scheduler.py
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Set

class SafeCleanupScheduler:
    """Cleanup scheduler with safety mechanisms"""
    
    def __init__(self, client, config: Dict):
        self.client = client
        self.config = config
        self.cleanup_lock = threading.Lock()
        self.active_operations = set()  # Track what's being cleaned
        self.rate_limiter = RateLimiter(config["rate_limit"])
        
    def schedule_cleanup(self):
        """Run periodic cleanup with safety checks"""
        if not self.cleanup_lock.acquire(blocking=False):
            # Already running
            return
            
        try:
            # Run cleanup tasks in priority order
            self._cleanup_processed_messages()
            self._create_snapshot_if_needed()
            self._cleanup_old_snapshots()
            self._garbage_collect_chunks()
            self._check_storage_limits()
        finally:
            self.cleanup_lock.release()
            
    def _cleanup_processed_messages(self):
        """Delete old messages with active download detection"""
        cutoff = datetime.now() - timedelta(days=self.config["inbox_retention_days"])
        
        # Get list of processed messages
        messages = self._list_processed_messages(before=cutoff)
        
        for batch in self._batch(messages, 50):
            # Check if any peer is currently downloading
            if self._any_peer_active(batch):
                continue  # Skip this batch
                
            # Mark as being deleted
            for msg in batch:
                self.active_operations.add(f"delete:{msg}")
                
            try:
                # Delete with verification
                deleted = self._delete_messages_safely(batch)
                self._log_cleanup("messages", deleted, len(batch))
            finally:
                # Remove from active operations
                for msg in batch:
                    self.active_operations.discard(f"delete:{msg}")
                    
            # Rate limit
            self.rate_limiter.wait()
            
    def _create_snapshot_if_needed(self):
        """Create snapshot with timing checks"""
        last_snapshot = self._get_last_snapshot_time()
        interval = timedelta(hours=self.config["snapshot_interval_hours"])
        
        if datetime.now() - last_snapshot > interval:
            # Check if state is stable (no recent changes)
            if self._state_is_stable():
                with self.state_manager.create_snapshot() as snapshot_id:
                    self._log_event("snapshot_created", snapshot_id)
                    
    def _garbage_collect_chunks(self):
        """Safely garbage collect with reference counting"""
        # Get all active manifests (current + snapshots)
        active_manifests = self._get_all_active_manifests()
        
        # Add safety margin for in-flight operations
        grace_period = timedelta(hours=self.config["safety"]["chunk_grace_period_hours"])
        
        # Let content store handle the actual GC with safety
        deleted = self.content_store.garbage_collect(
            active_manifests,
            grace_period=grace_period,
            dry_run=self.config["safety"]["dry_run"]
        )
        
        self._log_cleanup("chunks", deleted, None)
        
    def _check_storage_limits(self):
        """Monitor and enforce storage limits"""
        usage = self._calculate_storage_usage()
        limit = self.config["max_storage_mb"] * 1024 * 1024
        
        if usage > limit:
            # Emergency cleanup - oldest data first
            self._emergency_cleanup(usage - limit)
            
        # Send alert if approaching limit
        if usage > limit * 0.9:
            self._send_storage_alert(usage, limit)

class RateLimiter:
    """Rate limiter for Drive API calls"""
    
    def __init__(self, config: Dict):
        self.operations_per_minute = config["operations_per_minute"]
        self.backoff_multiplier = config["backoff_multiplier"]
        self.operation_times = []
        self.current_backoff = 0
        
    def wait(self):
        """Wait if necessary to stay under rate limit"""
        now = time.time()
        
        # Clean old operations
        cutoff = now - 60
        self.operation_times = [t for t in self.operation_times if t > cutoff]
        
        # Check if we need to wait
        if len(self.operation_times) >= self.operations_per_minute:
            wait_time = 60 - (now - self.operation_times[0])
            if wait_time > 0:
                time.sleep(wait_time + self.current_backoff)
                self.current_backoff *= self.backoff_multiplier
            else:
                self.current_backoff = 0
                
        self.operation_times.append(now)
```

### Phase 4: Query Optimization

#### 4.1 Incremental Index Generation

```python
# indexer.py
import json
import mmap
from typing import Dict, Any, Set, List

class IncrementalIndexer:
    """Build indexes incrementally to avoid memory issues"""
    
    def __init__(self, max_memory_mb: int = 100):
        self.max_memory = max_memory_mb * 1024 * 1024
        self.index_cache = {}
        
    def build_indexes(self, manifest: Dict, previous_indexes: Dict = None) -> Dict[str, Any]:
        """Build indexes incrementally from previous version"""
        # Only process changed files
        changed_files = self._detect_changes(manifest, previous_indexes)
        
        # Load existing indexes
        indexes = previous_indexes or {
            'by_date': {},
            'by_type': {},
            'by_size': {},
            'by_prefix': {}  # For efficient path queries
        }
        
        # Update indexes for changed files
        for path, file_info in changed_files.items():
            self._update_file_indexes(indexes, path, file_info)
            
        # Compact indexes if too large
        if self._estimate_size(indexes) > self.max_memory:
            indexes = self._compact_indexes(indexes)
            
        return indexes
        
    def _update_file_indexes(self, indexes: Dict, path: str, file_info: Dict):
        """Update all indexes for a single file"""
        # Date index (bucketed by day)
        date_key = file_info["modified"][:10]  # YYYY-MM-DD
        if date_key not in indexes["by_date"]:
            indexes["by_date"][date_key] = []
        indexes["by_date"][date_key].append(path)
        
        # Type index
        ext = path.rsplit('.', 1)[-1] if '.' in path else 'none'
        if ext not in indexes["by_type"]:
            indexes["by_type"][ext] = []
        indexes["by_type"][ext].append(path)
        
        # Size index (logarithmic buckets)
        size_bucket = self._get_size_bucket(file_info["size"])
        if size_bucket not in indexes["by_size"]:
            indexes["by_size"][size_bucket] = []
        indexes["by_size"][size_bucket].append(path)
        
        # Prefix index (for path queries)
        path_parts = path.split('/')
        for i in range(1, len(path_parts)):
            prefix = '/'.join(path_parts[:i])
            if prefix not in indexes["by_prefix"]:
                indexes["by_prefix"][prefix] = []
            indexes["by_prefix"][prefix].append(path)
            
    def _compact_indexes(self, indexes: Dict) -> Dict:
        """Compact indexes to save memory"""
        compacted = {}
        
        for index_type, index_data in indexes.items():
            if index_type == "by_prefix":
                # Keep only top-level prefixes
                compacted[index_type] = {
                    k: v for k, v in index_data.items()
                    if k.count('/') <= 2
                }
            else:
                # Keep only buckets with many items
                compacted[index_type] = {
                    k: v for k, v in index_data.items()
                    if len(v) > 10
                }
                
        return compacted

#### 4.2 Query API with Performance Optimization

```python
# query_api.py
class OptimizedStateQuery:
    """Query state with performance optimizations"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.query_cache = LRUCache(max_size=1000)
        self.index_loader = IndexLoader()
        
    def query(self, criteria: Dict, limit: int = None) -> List[str]:
        """Query files with caching and optimization"""
        # Check cache
        cache_key = self._criteria_to_key(criteria)
        if cache_key in self.query_cache:
            cached = self.query_cache[cache_key]
            return cached[:limit] if limit else cached
            
        # Load only needed indexes
        needed_indexes = self._determine_needed_indexes(criteria)
        indexes = self.index_loader.load_partial(needed_indexes)
        
        # Execute query with early termination
        results = self._execute_query(criteria, indexes, limit)
        
        # Cache results
        self.query_cache[cache_key] = results
        
        return results
        
    def _execute_query(self, criteria: Dict, indexes: Dict, limit: int) -> List[str]:
        """Execute query with optimizations"""
        candidate_sets = []
        
        # Use indexes to get candidate sets
        if "modified_after" in criteria:
            candidates = self._query_by_date(
                indexes["by_date"], 
                criteria["modified_after"],
                limit
            )
            candidate_sets.append(set(candidates))
            
        if "type" in criteria:
            ext = criteria["type"]
            if ext in indexes["by_type"]:
                candidate_sets.append(set(indexes["by_type"][ext]))
                
        if "path_prefix" in criteria:
            prefix = criteria["path_prefix"].rstrip('/')
            candidates = []
            for key, paths in indexes["by_prefix"].items():
                if key.startswith(prefix):
                    candidates.extend(paths)
            candidate_sets.append(set(candidates))
            
        # Intersect all candidate sets
        if candidate_sets:
            results = candidate_sets[0]
            for candidates in candidate_sets[1:]:
                results &= candidates
                if limit and len(results) <= limit:
                    break  # Early termination
                    
            return list(results)[:limit] if limit else list(results)
        else:
            # Full scan fallback
            return self._full_scan(criteria, limit)
            
    def stream_query(self, criteria: Dict) -> Iterator[str]:
        """Stream query results for memory efficiency"""
        # Load manifest header only
        manifest_meta = self.state_manager.get_manifest_metadata()
        
        # Stream through file entries
        for path in self.state_manager.stream_file_paths():
            file_info = self.state_manager.get_file_info(path)
            if self._matches_criteria(file_info, criteria):
                yield path

# Clock synchronization helper
class ClockSyncManager:
    """Handle clock skew between peers"""
    
    def __init__(self):
        self.peer_offsets = {}  # peer -> time offset
        
    def calculate_offset(self, peer_email: str, peer_time: float) -> float:
        """Calculate time offset for peer"""
        local_time = time.time()
        offset = peer_time - local_time
        
        # Store offset with exponential moving average
        if peer_email in self.peer_offsets:
            old_offset = self.peer_offsets[peer_email]
            self.peer_offsets[peer_email] = 0.9 * old_offset + 0.1 * offset
        else:
            self.peer_offsets[peer_email] = offset
            
        return self.peer_offsets[peer_email]
        
    def adjust_timestamp(self, timestamp: float, peer_email: str) -> float:
        """Adjust timestamp for clock skew"""
        offset = self.peer_offsets.get(peer_email, 0)
        return timestamp - offset
```

## Storage Optimization Strategy

### Storage Calculation

```
Free tier: 15 GB per Google account
Target usage: 10 GB (leaving buffer)

Per peer allocation:
- Active state: 100 MB
- 4 weekly snapshots: 400 MB  
- Inbox/outbox buffer: 100 MB
- Total per peer: ~600 MB

Supported peers: ~16 per account

With aggressive cleanup (1 week history):
- Active state: 100 MB
- 1 snapshot: 100 MB
- Inbox/outbox buffer: 50 MB
- Total per peer: ~250 MB

Supported peers: ~40 per account
```

### Cleanup Rules

1. **Inbox Messages**: Delete after processing + 24 hours
2. **Outbox Messages**: Delete after peer acknowledgment + 24 hours  
3. **Archive Messages**: Delete after 7 days
4. **Snapshots**: Keep last 4 weekly snapshots
5. **Chunks**: Garbage collect unreferenced chunks weekly

## Migration Strategy

1. **Backward Compatibility**: State system runs alongside existing inbox/outbox
2. **Gradual Rollout**: Enable for new peers first
3. **Data Migration**: Create initial state from existing files
4. **Feature Flag**: Allow disabling state system if needed

## Benefits

1. **Cost Efficiency**: Stay within Google Drive free tier
2. **Performance**: Sparse loading reduces bandwidth usage
3. **Scalability**: Support more peers with less storage
4. **Reliability**: Snapshots provide recovery points
5. **Query Speed**: Indexed state enables fast searches

## Future Enhancements

1. **Differential Snapshots**: Store only changes between snapshots
2. **Compression**: Compress manifest and chunks
3. **Encryption**: Encrypt state for privacy
4. **Multi-Transport**: Replicate state across transports
5. **P2P State Exchange**: Direct state sync between peers

## Implementation Timeline

- **Week 1-2**: State infrastructure (Phase 1)
- **Week 3-4**: State synchronization (Phase 2)
- **Week 5**: Automatic cleanup (Phase 3)
- **Week 6**: Query optimization (Phase 4)
- **Week 7**: Testing and migration
- **Week 8**: Documentation and rollout

## Security and Privacy

### 5.1 Access Control

```python
# access_control.py
class StateAccessControl:
    """Control access to state data"""
    
    def __init__(self, client):
        self.client = client
        self.access_rules = {}
        
    def validate_manifest_access(self, manifest: Dict, peer_email: str) -> bool:
        """Validate peer has access to manifest"""
        # Check manifest owner
        if manifest["owner"] != peer_email:
            return False
            
        # Check signature if present
        if "signature" in manifest:
            return self._verify_signature(manifest, peer_email)
            
        return True
        
    def filter_manifest_for_peer(self, manifest: Dict, peer_email: str) -> Dict:
        """Filter manifest to only show allowed paths"""
        allowed_paths = self._get_allowed_paths(peer_email)
        
        filtered = manifest.copy()
        filtered["files"] = {
            path: info for path, info in manifest["files"].items()
            if any(path.startswith(allowed) for allowed in allowed_paths)
        }
        
        return filtered
```

### 5.2 Metadata Privacy

```python
# privacy_filter.py
class MetadataPrivacyFilter:
    """Filter sensitive metadata from manifests"""
    
    def __init__(self, privacy_level: str = "standard"):
        self.privacy_level = privacy_level
        self.sensitive_patterns = [
            r"\.ssh/",
            r"\.gnupg/",
            r"private/",
            r"secret",
        ]
        
    def sanitize_manifest(self, manifest: Dict) -> Dict:
        """Remove sensitive metadata based on privacy level"""
        if self.privacy_level == "paranoid":
            # Only expose file existence, not metadata
            return self._paranoid_filter(manifest)
        else:
            # Standard filtering
            return self._standard_filter(manifest)
            
    def _standard_filter(self, manifest: Dict) -> Dict:
        """Standard privacy filtering"""
        filtered = manifest.copy()
        
        # Filter sensitive paths
        filtered["files"] = {
            path: self._sanitize_file_info(info)
            for path, info in manifest["files"].items()
            if not self._is_sensitive_path(path)
        }
        
        return filtered
```

## Monitoring and Observability

### 6.1 Health Monitoring

```python
# health_monitor.py
class StateHealthMonitor:
    """Monitor state system health"""
    
    def __init__(self, client):
        self.client = client
        self.metrics = {
            "manifest_updates": 0,
            "query_latency": [],
            "sync_errors": 0,
            "storage_usage": 0,
            "cleanup_runs": 0
        }
        self.alerts = []
        
    def check_health(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        return {
            "manifest_integrity": self._check_manifest_integrity(),
            "storage_usage": self._check_storage_usage(),
            "sync_status": self._check_sync_status(),
            "performance": self._check_performance(),
            "errors": self._get_recent_errors()
        }
        
    def _check_manifest_integrity(self) -> Dict:
        """Verify manifest integrity"""
        try:
            manifest = self.state_manager.get_current_manifest()
            is_valid = self.state_manager._validate_manifest(manifest)
            
            # Check vector clock consistency
            vc_consistent = self._check_vector_clock_consistency(manifest)
            
            return {
                "valid": is_valid,
                "vector_clock_consistent": vc_consistent,
                "last_updated": manifest["timestamp"]
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}
            
    def _check_storage_usage(self) -> Dict:
        """Monitor storage usage trends"""
        current = self._calculate_current_usage()
        trend = self._calculate_usage_trend()
        
        return {
            "current_mb": current / 1024 / 1024,
            "limit_mb": self.config["max_storage_mb"],
            "usage_percent": (current / (self.config["max_storage_mb"] * 1024 * 1024)) * 100,
            "trend": trend,
            "projected_days_to_limit": self._project_days_to_limit(current, trend)
        }
```

### 6.2 Audit Logging

```python
# audit_logger.py
class StateAuditLogger:
    """Audit all state operations"""
    
    def __init__(self, log_path: str):
        self.log_path = log_path
        self.current_log = []
        
    def log_operation(self, operation: str, details: Dict):
        """Log state operation with context"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "user": self.client.email,
            "details": details,
            "trace_id": self._generate_trace_id()
        }
        
        self.current_log.append(entry)
        
        # Flush to disk periodically
        if len(self.current_log) > 100:
            self._flush_log()
            
    def query_audit_log(self, criteria: Dict) -> List[Dict]:
        """Query audit log for analysis"""
        # Implementation for querying logs
        pass
```

## Migration and Rollback

### 7.1 Version Migration

```python
# version_migrator.py
class StateMigrator:
    """Handle migrations between state versions"""
    
    MIGRATIONS = {
        "1.0": {
            "1.1": "_migrate_1_0_to_1_1",
            "2.0": "_migrate_1_0_to_2_0"
        }
    }
    
    def migrate_manifest(self, manifest: Dict, target_version: str) -> Dict:
        """Migrate manifest to target version"""
        current_version = manifest["version"]
        
        if current_version == target_version:
            return manifest
            
        # Find migration path
        path = self._find_migration_path(current_version, target_version)
        if not path:
            raise ValueError(f"No migration path from {current_version} to {target_version}")
            
        # Apply migrations in sequence
        result = manifest.copy()
        for from_v, to_v in path:
            migration_func = getattr(self, self.MIGRATIONS[from_v][to_v])
            result = migration_func(result)
            result["version"] = to_v
            
        return result
        
    def _migrate_1_0_to_1_1(self, manifest: Dict) -> Dict:
        """Example migration adding new fields"""
        migrated = manifest.copy()
        
        # Add vector clock if missing
        if "vector_clock" not in migrated:
            migrated["vector_clock"] = {migrated["owner"]: 1}
            
        # Add sequence number
        if "sequence_number" not in migrated:
            migrated["sequence_number"] = 1
            
        return migrated
```

### 7.2 Rollback Support

```python
# rollback_manager.py
class RollbackManager:
    """Support rolling back to previous states"""
    
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.rollback_points = []
        
    def create_rollback_point(self, reason: str) -> str:
        """Create a rollback point before risky operations"""
        rollback_id = f"rollback_{int(time.time())}"
        
        # Create special snapshot
        snapshot_id = self.state_manager.create_snapshot(
            metadata={"rollback_id": rollback_id, "reason": reason}
        )
        
        self.rollback_points.append({
            "id": rollback_id,
            "snapshot_id": snapshot_id,
            "timestamp": datetime.now(),
            "reason": reason
        })
        
        return rollback_id
        
    def rollback(self, rollback_id: str, dry_run: bool = True) -> Dict:
        """Rollback to a previous state"""
        rollback_point = next(
            (rp for rp in self.rollback_points if rp["id"] == rollback_id),
            None
        )
        
        if not rollback_point:
            raise ValueError(f"Rollback point {rollback_id} not found")
            
        if dry_run:
            # Show what would be changed
            return self._preview_rollback(rollback_point)
        else:
            # Perform actual rollback
            return self._execute_rollback(rollback_point)
```

## Performance Optimizations

### 8.1 Caching Strategy

```python
# cache_manager.py
class StateCacheManager:
    """Multi-level caching for state data"""
    
    def __init__(self, memory_mb: int = 100):
        self.memory_cache = LRUCache(max_size_mb=memory_mb)
        self.disk_cache = DiskCache(max_size_gb=1)
        self.bloom_filters = {}  # Quick existence checks
        
    def get_with_cache(self, key: str, loader_func):
        """Get with multi-level cache"""
        # L1: Memory cache
        if key in self.memory_cache:
            return self.memory_cache[key]
            
        # L2: Disk cache
        if key in self.disk_cache:
            value = self.disk_cache[key]
            self.memory_cache[key] = value
            return value
            
        # L3: Load from source
        value = loader_func()
        self.memory_cache[key] = value
        self.disk_cache[key] = value
        
        return value
```

### 8.2 Batch Operations

```python
# batch_processor.py
class BatchProcessor:
    """Batch operations for efficiency"""
    
    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size
        self.pending_operations = defaultdict(list)
        
    def add_operation(self, op_type: str, data: Any):
        """Add operation to batch"""
        self.pending_operations[op_type].append(data)
        
        if len(self.pending_operations[op_type]) >= self.batch_size:
            self.flush_operations(op_type)
            
    def flush_operations(self, op_type: str = None):
        """Execute batched operations"""
        if op_type:
            ops = self.pending_operations[op_type]
            if ops:
                self._execute_batch(op_type, ops)
                self.pending_operations[op_type] = []
        else:
            # Flush all
            for op_type, ops in self.pending_operations.items():
                if ops:
                    self._execute_batch(op_type, ops)
            self.pending_operations.clear()
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|---------|------------|
| **Race Conditions** | High | Distributed locking, atomic operations, vector clocks |
| **Storage Overflow** | High | Aggressive cleanup, monitoring, storage alerts |
| **State Corruption** | High | Checksums, validation, snapshot recovery |
| **Sync Conflicts** | Medium | Conflict resolution, vector clock ordering |
| **API Rate Limits** | Medium | Rate limiting, exponential backoff, batching |
| **Performance Degradation** | Medium | Incremental indexes, caching, query optimization |
| **Clock Skew** | Medium | Clock sync manager, timestamp adjustment |
| **Data Loss** | High | Multiple snapshots, rollback points, audit logs |
| **Security Breaches** | High | Access control, metadata filtering, encryption |
| **Version Incompatibility** | Medium | Version migration, backward compatibility |
| **Silent Failures** | High | Health monitoring, alerts, audit logging |
| **Echo Amplification** | Medium | Echo suppression, sync history integration |

## Success Metrics

- Storage per peer < 500 MB average
- State query time < 100ms
- Sync time for new peer < 30 seconds
- Zero data loss incidents
- 90% reduction in message processing for queries

## Implementation Summary

### Key Design Decisions

1. **Hybrid Architecture**: State system complements existing message system rather than replacing it
2. **Content Addressing**: Enables deduplication and efficient storage
3. **Vector Clocks**: Provide causal ordering for distributed updates
4. **Distributed Locking**: Uses Drive-native locking for consistency
5. **Incremental Updates**: Only changed files update indexes
6. **Multi-Level Caching**: Memory, disk, and bloom filters for performance
7. **Graceful Degradation**: Falls back to message system if state unavailable

### Integration Points

1. **Message System Bridge**: Prevents loops between state and message systems
2. **Sync History**: Leverages existing echo prevention
3. **Transport Layer**: Reuses existing Drive transport infrastructure
4. **File Watcher**: Integrated to trigger state updates

### Safety Mechanisms

1. **Atomic Operations**: All updates use temp files + rename
2. **Validation**: Checksums and version checks on every read
3. **Grace Periods**: Cleanup waits before deleting
4. **Rate Limiting**: Prevents API quota exhaustion
5. **Rollback Points**: Can recover from bad updates
6. **Health Monitoring**: Proactive issue detection

### Expected Outcomes

1. **Performance**: 10-100x faster queries vs processing messages
2. **Cost**: Stay within Google Drive free tier for most users
3. **Reliability**: Multiple recovery mechanisms prevent data loss
4. **Scalability**: Support 40+ peers per Google account
5. **User Experience**: Near-instant file browsing and search