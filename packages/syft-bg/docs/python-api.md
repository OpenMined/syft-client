# syft-bg Python API

```python
import syft_bg
```

## Init

```python
syft_bg.init(email="you@example.com", start=True)
```

Creates config and starts the background services (notify + approve).
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
    file_names=["params.json"],
    peers=["charlie@org.com"],
)
```

Registers scripts for auto-approval. Jobs matching these scripts from listed peers get approved automatically.

- `contents` — `.py` files (or directories) to approve
- `file_names` — non-`.py` files to allow (e.g. data files)
- `peers` — restrict to these emails. Omit to allow any peer
- `name` — optional name for the approval object

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
    file_names=["params.json"],
    peers=["alice@uni.edu"],
)

# Check everything
syft_bg.status

# After kernel restart, recover services
syft_bg.ensure_running()
```
