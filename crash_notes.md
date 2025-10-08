# File Watcher Crash Analysis

## Crash Summary
- **Date**: 2025-10-07 21:42:38
- **Process**: Python watcher process
- **Crash Type**: Memory corruption (SIGABRT)
- **Error**: `free_list_checksum_botch` in malloc
- **Thread**: Crashed in thread 10 during `builtin_compile`
- **Scenario**: Stress testing with 3 jobs every 40 seconds

## Root Cause Theories

### Theory 1: Race Condition in Multi-threaded File Operations (Most Likely)
- Multiple threads processing file system events simultaneously
- Shared data structures accessed without proper locking
- One thread freed memory another was still using
- Evidence: `free_list_checksum_botch` indicates double-free or use-after-free

### Theory 2: Memory Pressure from Rapid Job Processing
- 3 jobs/40 seconds creates significant memory allocation
- Garbage collector not keeping up with allocation rate
- Memory fragmentation accumulating over time
- Evidence: Error in `small_free_list_remove_ptr_no_clear`

### Theory 3: File System Event Buffer Overflow
- FSEvents buffers overflow when events arrive too fast
- Corrupted event data leads to invalid operations
- Evidence: Thread 8 actively reading events during crash

## Remediation Strategies

### 1. Thread-Safe Queue with Worker Pool Pattern
**Implementation:**
```python
import queue
import threading

# Single thread receives events
event_queue = queue.Queue(maxsize=1000)

# Worker pool processes events
for i in range(4):
    worker = threading.Thread(target=process_events, args=(event_queue,))
    worker.start()
```

**Benefits:**
- Eliminates race conditions
- Natural backpressure mechanism
- Easier debugging with serialized flow

### 2. Aggressive Memory Management
**Implementation:**
```python
import gc
import psutil

# After batch processing
gc.collect()

# Monitor memory usage
if psutil.Process().memory_percent() > 80:
    # Pause processing or restart

# Use context managers
with open(file_path) as f:
    # Process file

# Weak references for caches
import weakref
cache = weakref.WeakValueDictionary()
```

**Benefits:**
- Prevents memory exhaustion
- Reduces fragmentation
- Makes leaks visible

### 3. Process Isolation with Automatic Recovery
**Implementation:**
```python
import subprocess
import time

def supervise_watcher():
    while True:
        try:
            # Start watcher subprocess
            proc = subprocess.Popen(['python', 'watcher.py'])
            proc.wait()
        except:
            pass
        
        # Exponential backoff
        time.sleep(min(retry_count * 2, 60))
        retry_count += 1
```

**Benefits:**
- Crashes don't affect main app
- Automatic recovery
- Resource isolation
- Can set memory/CPU limits

## Recommended Solution
Implement all three strategies:
1. Queue-based architecture for thread safety
2. Aggressive memory management within the worker
3. Run entire system in supervised subprocess

This creates multiple layers of protection against both the root cause and its effects.

## Quick Fixes to Try First
1. Add `gc.collect()` calls after processing batches
2. Limit concurrent threads processing events
3. Add try/except blocks around all file operations
4. Increase time between event processing