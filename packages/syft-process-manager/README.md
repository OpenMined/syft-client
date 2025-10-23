# syft-process-manager

A Python library for managing long-running background processes with built-in logging, health checks, and Jupyter notebook integration.

## Features

- Start, stop, and monitor background processes
- Run Python functions as detached processes with cloudpickle
- Stream stdout/stderr logs
- Persistent state across Python sessions
- Interactive Jupyter widgets with live log streaming
- Optional TTL and health checks
- PID reuse protection using creation timestamps

## Installation

```bash
pip install syft-process-manager
```

## Quick Start

### Running Commands

```python
import syft_process_manager as syftpm

# Start a process
handle = syftpm.run(
    name="my-server",
    cmd=["python", "-m", "http.server", "8000"]
)

# Check status and view logs
print(handle.status)  # "running"
print(handle.pid)
print(handle.stdout.tail(10))

# Terminate
handle.terminate()
```

### Running Python Functions

```python
import time
from syft_process_manager import run_function

def my_background_task(message):
    i = 0
    while True:
        print(f"Iteration {i}: {message}")
        i += 1
        time.sleep(1)

# Run in background with auto-termination
handle = run_function(
    my_background_task,
    message="Hello from background!",
    name="my-task",
    ttl_seconds=120,
)

print(handle.uptime)
print(handle.stdout.tail())
```

### Managing Multiple Processes

```python
from syft_process_manager import ProcessManager

pm = ProcessManager()

# Start multiple processes
pm.create_and_run(name="worker-1", cmd=["python", "worker.py"])
pm.create_and_run(name="worker-2", cmd=["python", "worker.py"])

# List all processes
for handle in pm.list():
    print(f"{handle.name}: {handle.status} (PID: {handle.pid})")

# Cleanup
pm.terminate_all()
```

## Core Components

### ProcessManager

Main entry point for creating and managing processes. Maintains a registry in `~/.syft-process-manager` by default.

### ProcessHandle

Represents a managed process with methods:

- `start()`, `terminate()`, `is_running()`, `refresh()`, `info()`

Key properties:

- `status`: "running", "stopped", or "unhealthy"
- `pid`, `uptime`: Process information
- `stdout`, `stderr`: LogStream objects
- `health`: Optional health check data

### LogStream

Access process logs with `tail(n)`, `head(n)`, or `read_lines()`.

## Advanced Features

```python
# Custom environment variables
handle = syftpm.run(
    name="my-app",
    cmd=["python", "app.py"],
    env={"DEBUG": "true"}
)

# Replace existing process
handle = syftpm.run(
    name="my-app",
    cmd=["python", "app.py"],
    overwrite=True
)

# TTL (auto-terminate)
handle = syftpm.run_function(
    my_task,
    ttl_seconds=3600,
    name="temporary-task"
)
```

### Health Checks

Write health information from your process:

```python
import json, os
from pathlib import Path

process_dir = Path(os.environ["SYFTPM_PROCESS_DIR"])
(process_dir / "health.json").write_text(json.dumps({
    "timestamp": "2025-01-15T12:00:00Z",
    "status": "healthy",
    "details": {"requests_served": 1234}
}))

# Read from manager
health = handle.health
```

## Jupyter Notebook Integration

ProcessHandle objects automatically render as interactive widgets with real-time status updates, live log streaming, and theme-aware styling:

```python
handle = syftpm.run(name="notebook-server", cmd=["python", "app.py"])
handle  # Displays interactive widget
```
