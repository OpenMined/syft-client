# anywidget Migration Plan

## Overview

Migrate from HTTP polling architecture to `anywidget` with Python-side polling (push model) to support Google Colab and other remote notebook environments.

## Current Architecture (HTTP Polling - Pull Model)

**Components:**

- Python: ProcessHandle with `_repr_html_()` → renders HTML + injects JavaScript
- FastAPI backend: Runs on localhost, serves log file content via REST endpoints
- JavaScript: Polls backend every second for stdout/stderr updates

**Problem:**

- JavaScript polls `http://localhost:{port}` which works locally
- In Colab: widget JS runs in user's browser, backend runs on Colab VM
- `localhost` in browser ≠ `localhost` on Colab VM → polling fails

## New Architecture (anywidget - Push Model)

**Components:**

- Python: `anywidget.AnyWidget` subclass with synchronized traits
- Python background thread: Polls process state/logs, updates traits
- JavaScript: Reactive rendering based on trait changes (no HTTP calls)

**Advantages:**

- Communication via Jupyter comm protocol (works everywhere)
- Simpler: one polling loop in Python vs multiple fetch calls in JS
- Better resource control and error handling
- No FastAPI server needed

## Implementation Plan

### 1. Define Widget Class Structure

Create new file: `src/syft_process_manager/display/anywidget_impl.py`

**Python traits to synchronize:**

```python
class ProcessWidget(anywidget.AnyWidget):
    # Static info
    name = traitlets.Unicode().tag(sync=True)
    process_dir = traitlets.Unicode().tag(sync=True)

    # Dynamic process state
    status = traitlets.Unicode("unknown").tag(sync=True)
    pid = traitlets.Int(allow_none=True, default_value=None).tag(sync=True)
    uptime = traitlets.Unicode("-").tag(sync=True)

    # Health info
    health_status = traitlets.Unicode(allow_none=True, default_value=None).tag(sync=True)
    health_message = traitlets.Unicode(allow_none=True, default_value=None).tag(sync=True)

    # Logs (list of strings)
    stdout_lines = traitlets.List(trait=traitlets.Unicode()).tag(sync=True)
    stderr_lines = traitlets.List(trait=traitlets.Unicode()).tag(sync=True)

    # Theme
    theme = traitlets.Unicode("light").tag(sync=True)  # "light" or "dark"

    # Control
    polling_active = traitlets.Bool(True).tag(sync=True)
```

### 2. Python-Side Polling (Push Model)

**Background thread:**

- Runs while widget is alive
- Polls every 1 second
- Updates all traits in one cycle
- Thread stops when widget is garbage collected or explicitly stopped

**Data flow:**

```
Process state files → Python reads → Update traits → Auto-sync to JS
```

**What to poll:**

1. **PID + process state**: `handle.refresh()` + `handle.is_running()`
2. **Health file**: `handle.health` (if exists)
3. **Stdout**: `handle.stdout.tail(20)`
4. **Stderr**: `handle.stderr.tail(20)`
5. **Uptime**: `handle.uptime`

### 3. JavaScript Rendering (Reactive)

Create new file: `src/syft_process_manager/assets/widget.js`

**Structure:**

- ESM module with `render()` function
- Listens to trait changes via `model.on("change:*", ...)`
- Updates DOM reactively (no HTTP fetch calls)
- Preserves current visual design from `process_widget.html`

**Behavior:**

- Auto-scroll logs if user is at bottom (preserve existing UX)
- Apply theme colors based on `theme` trait
- Status icons and colors based on `status` trait
- Handle empty/loading states gracefully

**Key differences from current JS:**

- NO `fetch()` calls
- NO `setInterval()` for polling
- Pure reactive updates: `model.get("stdout_lines")` whenever trait changes

### 4. Integration with ProcessHandle

Modify `handle.py`:

- Replace `_repr_html_()` with `_repr_mimebundle_()`
- Return widget instance instead of HTML string
- Widget automatically starts polling when created

### 5. Cleanup

**Remove:**

- `display/backend_app.py` (entire FastAPI backend)
- `assets/log_polling.js` (HTTP polling script)
- `display/widget.py` (Jinja2 template rendering)
- `assets/process_widget.html` (move inline styles to widget.js)

**Update dependencies:**

- Add: `anywidget`
- Remove: `fastapi`, `uvicorn`, `jinja2`

### 6. Theme Detection

Keep dark mode detection but pass as trait:

```python
from jupyter_dark_detect import is_dark  # optional
widget.theme = "dark" if is_dark() else "light"
```

JavaScript applies colors based on `theme` trait value.

## Migration Checklist

- [ ] Install anywidget dependency
- [ ] Create `ProcessWidget` class with all traits
- [ ] Implement Python-side polling thread
- [ ] Create ESM module for JavaScript rendering
- [ ] Preserve visual design (colors, layout, icons)
- [ ] Preserve UX (auto-scroll, status indicators)
- [ ] Update `ProcessHandle._repr_html_()` → `_repr_mimebundle_()`
- [ ] Test locally in Jupyter
- [ ] Test in Google Colab
- [ ] Remove old backend/template code
- [ ] Update dependencies in pyproject.toml

## Testing Strategy

1. **Local Jupyter**: Verify basic functionality
2. **Google Colab**: Verify polling works (primary goal)
3. **VSCode notebooks**: Verify compatibility
4. **Multiple widgets**: Test simultaneous instances
5. **Long-running processes**: Test uptime/log updates
6. **Process lifecycle**: Test start/stop/health changes

## Open Questions

- Polling frequency: Keep 1 second or make configurable?
- Thread cleanup: Rely on daemon thread or explicit stop?
- Log line limit: Keep 20 lines or make configurable?
- Health check display: Show full health object or just status?
