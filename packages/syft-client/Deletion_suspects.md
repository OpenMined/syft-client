# Potential Deletion Sources for Echo Problem

## Most Likely Suspects

### 1. Message Cleanup (transport_base.py)
- **Line 684**: `temp_file.unlink()` - Deletes archive after extraction
- **Line 687**: `shutil.rmtree(extracted_dir)` - **Deletes entire message directory**

### 2. Deletion Processing (transport_base.py)
- **Line 562**: `path_to_delete.unlink()` - Processes incoming deletion messages
- **Line 558**: `shutil.rmtree(path_to_delete)` - Deletes directories from deletion messages

### 3. Archive Creation Cleanup (sender.py)
- **Line 161**: `shutil.rmtree(temp_dir)` - Cleans up temp dir after sending
- **Line 328**: `shutil.rmtree(temp_dir)` - Cleans up after deletion message

### 4. Message Processing (message_processor.py)
- **Line 123**: `dest.unlink()` - Deletes existing file before overwrite
- **Line 119**: `shutil.rmtree(dest)` - Removes existing directory

### 5. Atomic Replace Operations
- **transport_base.py:663**: `temp_dest.replace(dest)` - Atomic file replacement
- **transport_base.py:787**: `temp_dest.replace(d)` - Atomic replacement in merge

