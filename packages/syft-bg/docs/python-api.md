# syft-bg Python API

```python
import syft_bg
```

## Init

```python
syft_bg.init(email="you@example.com", start=True)
```

Creates config and starts the background services (sync + notify + approve).
Use `start=False` to just create the config without starting.

## Status

```python
syft_bg.status
```

Shows email, services, auto-approval objects, and environment info. No parentheses needed.

## Auto-approve

```python
syft_bg.auto_approve(
    contents=["main.py"],
    file_paths=["params.json"],
    peers=["charlie@org.com"],
)
```

Registers scripts for auto-approval. Jobs matching these scripts from listed peers get approved automatically.

- `contents` — files (or directories) to approve by content
- `file_paths` — files to allow by name only (e.g. data files)
- `peers` — restrict to these emails. Omit to allow any peer
- `name` — optional name for the approval object

## Auto-approve from job

```python
from syft_bg import auto_approve_job

job = do_manager.jobs[0]

# Default: all files matched by name + content
auto_approve_job(job)

# Only match data.json by name, everything else by content
auto_approve_job(job, file_paths=["data.json"])

# Only content-match main.py, ignore other files
auto_approve_job(job, contents=["main.py"])

# Explicit: main.py by content, data.json by name only
auto_approve_job(job, contents=["main.py"], file_paths=["data.json"])
```

Creates an auto-approval config from an existing job's files. Calls `auto_approve()` internally.

- `job` — `JobInfo` object to use as template
- `contents` — filenames from the job to match by name AND content. Default (None): all files are content-matched
- `file_paths` — filenames from the job to match by name only. When set, all other files are content-matched
- `peers` — restrict to these emails. Defaults to the job's submitter
- `name` — optional name for the approval object (defaults to job name)

## Authenticate

```python
syft_bg.authenticate()
```

Interactive OAuth setup for Gmail and Drive tokens. Run this if `init()` reports missing tokens.

## Service control

```python
syft_bg.start()           # start all services
syft_bg.stop()            # stop all services
syft_bg.restart()         # restart all services
syft_bg.ensure_running()  # start any stopped services
syft_bg.logs("sync")      # last 50 lines of sync service log
syft_bg.logs("approve")   # last 50 lines of approve service log
syft_bg.logs("notify")    # last 50 lines of notify service log
```

## Typical notebook flow

```python
import syft_bg

# First time setup
syft_bg.init(email="you@example.com", start=True)

# If tokens are missing
syft_bg.authenticate()

# Register scripts for auto-approval
syft_bg.auto_approve(
    contents=["main.py", "utils.py"],
    file_paths=["params.json"],
    peers=["alice@uni.edu"],
)

# Check everything
syft_bg.status

# After kernel restart, recover services
syft_bg.ensure_running()
```
