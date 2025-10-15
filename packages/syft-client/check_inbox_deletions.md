# Deletions Called During peer.check_inbox()

## Call Flow
`peer.check_inbox()` → `transport.check_inbox()` → `BaseTransportLayer.check_inbox()`

## Deletions That Occur

### 1. Failed Archive Extraction (transport_base.py:455)
**When:** If tar archive fails to extract
```python
except tarfile.ReadError as e:
    if verbose:
        print(f"   ❌ Failed to extract archive: {e}")
    # Skip this message
    temp_file.unlink()  # ← DELETION
    continue
```

### 2. Processing Deletion Messages (transport_base.py:558, 562)
**When:** Incoming message is a deletion request
```python
if path_to_delete.exists():
    if path_to_delete.is_dir():
        shutil.rmtree(path_to_delete)  # ← DELETION (directory)
        if verbose:
            print(f"   🗑️  Deleted directory: {path_to_delete.name}")
    else:
        path_to_delete.unlink()  # ← DELETION (file)
        if verbose:
            print(f"   🗑️  Deleted file: {path_to_delete.name}")
```

### 3. File Replacement During Extraction (transport_base.py:663)
**When:** Extracted file already exists at destination
```python
if dest.exists():
    # Use atomic replacement to prevent watcher from seeing deletion
    temp_dest = dest.with_suffix(f'.tmp.{int(time.time() * 1000000)}')
    shutil.move(str(item), str(temp_dest))
    # Atomic replace (on most filesystems)
    temp_dest.replace(dest)  # ← ATOMIC REPLACEMENT (may trigger delete+create events)
```

### 4. Message Cleanup - Archive File (transport_base.py:684)
**When:** After successfully processing a message
```python
# Clean up temporary files
temp_file.unlink()  # ← DELETION (archive .tar.gz file)
```

### 5. Message Cleanup - Extracted Directory (transport_base.py:687) ⚠️ MOST LIKELY CULPRIT
**When:** After successfully processing a message
```python
if extracted_dir.exists():
    import shutil
    shutil.rmtree(extracted_dir)  # ← DELETION (entire message directory)
```
**Why this is suspicious:**
- Deletes entire `msg_XXXXXX` directory after files are moved
- Directory is inside the watched SyftBox root
- Watcher sees these deletions recursively
- Could trigger deletion events for files that were just moved

### 6. Directory Merge Operations (transport_base.py:784)
**When:** Merging directories during file extraction
```python
if d.exists():
    # Use atomic replacement to prevent watcher from seeing deletion
    import time
    temp_dest = d.with_suffix(f'.tmp.{int(time.time() * 1000000)}')
    shutil.move(str(s), str(temp_dest))
    temp_dest.replace(d)  # ← ATOMIC REPLACEMENT
```

### 7. Message Processing by Receiver (if used)
**When:** If receiver's MessageProcessor is used instead of transport_base
```python
# In message_processor.py:119,123
if dest.exists():
    if dest.is_dir():
        shutil.rmtree(dest)  # ← DELETION (directory)
    else:
        dest.unlink()  # ← DELETION (file)
```

## Summary

During a typical `peer.check_inbox()` call, the following deletions occur:

1. **temp_file.unlink()** - Deletes the downloaded .tar.gz archive
2. **shutil.rmtree(extracted_dir)** - Deletes the extracted message directory
3. **Atomic replacements** - May trigger delete+create events for existing files
4. **Deletion message processing** - Only if the message contains deletion requests

The most problematic is likely #2 (`rmtree(extracted_dir)`) because:
- It happens AFTER files are moved to their destinations
- The directory is in the watched SyftBox root
- The recursive watcher might see internal deletions before the directory is removed
- This could explain why deletion events are being sent back to the original sender
