function render({ model, el }) {
  const container = document.createElement("div");
  container.className = "process-widget";
  el.appendChild(container);

  function buildInitialHTML() {
    const config = model.get("config");
    const name = config?.name || "Unknown";
    const processDir = config?.process_dir || "-";
    const ttl = config?.ttl_seconds ? `${config.ttl_seconds}s` : "-";
    const theme = model.get("theme");
    const themeClass = theme === "dark" ? "theme-dark" : "theme-light";

    container.innerHTML = `
      <div class="process-widget-container ${themeClass}">
        <div class="process-widget-header">
          <h3 class="process-widget-title">⚙️ ${name}</h3>
          <button class="process-widget-polling-btn" data-action="toggle-polling"></button>
        </div>

        <table class="process-widget-table">
          <tr>
            <td>Status:</td>
            <td class="process-widget-status" data-field="status"></td>
          </tr>
          <tr>
            <td>PID:</td>
            <td data-field="pid">-</td>
          </tr>
          <tr>
            <td>Uptime:</td>
            <td data-field="uptime">-</td>
          </tr>
          <tr>
            <td>Last Health Report:</td>
            <td data-field="health">never</td>
          </tr>
          <tr>
            <td>Process Dir:</td>
            <td>
              <a href="file://${processDir}" class="process-dir-link">
                ${processDir}
              </a>
            </td>
          </tr>
          <tr>
            <td>TTL:</td>
            <td>${ttl}</td>
          </tr>
        </table>

        <div class="process-widget-logs">
          <div class="process-widget-log-panel">
            <div class="process-widget-log-header">Recent logs:</div>
            <div class="process-widget-log-content log-container" data-logs="stdout"></div>
          </div>

          <div class="process-widget-log-panel">
            <div class="process-widget-log-header">Recent errors:</div>
            <div class="process-widget-log-content stderr log-container" data-logs="stderr"></div>
          </div>
        </div>
      </div>
    `;

    // polling toggle button
    const pollingBtn = container.querySelector(".process-widget-polling-btn");
    pollingBtn.onclick = () => {
      const isActive = model.get("polling_active");
      model.set("polling_active", !isActive);
      model.save_changes();
    };
  }

  function updateProcessInfo() {
    const processState = model.get("process_state");
    const health = model.get("health");

    const pid = processState?.pid || null;
    const uptime = formatTimeSince(processState?.created_at);
    const status = deriveStatus(processState, health);
    const lastHealthCheckTime = formatTimeSince(health?.timestamp);

    const statusIcons = {
      running: "✅",
      unhealthy: "⚠️",
      stopped: "⭕",
      unknown: "❓",
    };
    const statusIcon = statusIcons[status] || statusIcons["unknown"];

    // Update DOM elements
    const statusEl = container.querySelector('[data-field="status"]');
    if (statusEl) {
      statusEl.className = `process-widget-status ${status}`;
      statusEl.textContent = `${statusIcon} ${status}`;
    }
    const pidEl = container.querySelector('[data-field="pid"]');
    if (pidEl) pidEl.textContent = pid !== null ? pid : "-";

    const uptimeEl = container.querySelector('[data-field="uptime"]');
    if (uptimeEl) uptimeEl.textContent = uptime || "-";

    const healthEl = container.querySelector('[data-field="health"]');
    if (healthEl)
      healthEl.textContent = lastHealthCheckTime
        ? `${lastHealthCheckTime} ago`
        : "never";
  }

  function updateStdoutLogs() {
    const stdoutLines = model.get("stdout_lines");
    const stdoutContainer = container.querySelector('[data-logs="stdout"]');
    if (stdoutContainer) {
      stdoutContainer.innerHTML =
        stdoutLines && stdoutLines.length > 0
          ? stdoutLines
              .map((line) => `<span>${escapeHtml(line)}</span>`)
              .join("<br>")
          : '<em class="empty-log-message">No recent output</em>';
      stdoutContainer.scrollTop = stdoutContainer.scrollHeight;
    }
  }

  function updateStderrLogs() {
    const stderrLines = model.get("stderr_lines");
    const stderrContainer = container.querySelector('[data-logs="stderr"]');
    if (stderrContainer) {
      stderrContainer.innerHTML =
        stderrLines && stderrLines.length > 0
          ? stderrLines
              .map((line) => `<span>${escapeHtml(line)}</span>`)
              .join("<br>")
          : '<em class="empty-log-message">No recent errors</em>';
      stderrContainer.scrollTop = stderrContainer.scrollHeight;
    }
  }

  function updatePollingButton() {
    const pollingActive = model.get("polling_active");
    const pollingBtn = container.querySelector(".process-widget-polling-btn");
    if (pollingBtn) {
      pollingBtn.textContent = pollingActive
        ? "⏸ Pause Widget"
        : "▶️ Resume Widget";
    }
  }

  function deriveStatus(processState, health) {
    if (!processState || !processState.pid) {
      return "stopped";
    }
    if (health && health.status !== "healthy") {
      return "unhealthy";
    }
    return "running";
  }

  function formatTimeSince(timestamp) {
    if (!timestamp) return null;

    const then = new Date(timestamp);
    const now = new Date();
    const diffSeconds = Math.floor((now - then) / 1000);

    if (diffSeconds < 5) return "< 5s";
    if (diffSeconds < 60) return "< 1m";
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d`;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Initial render
  buildInitialHTML();
  updateProcessInfo();
  updateStdoutLogs();
  updateStderrLogs();
  updatePollingButton();

  // Polling in javascript for google colab compatibility
  // In colab, python background threads pause when idle
  let pollInterval = null;
  function startPolling() {
    if (pollInterval) return;

    const interval = model.get("polling_interval") * 1000 || 1000;
    pollInterval = setInterval(() => {
      const isActive = model.get("polling_active");
      if (isActive) {
        // Increment poll trigger to notify Python
        const currentTrigger = model.get("_poll_trigger") || 0;
        model.set("_poll_trigger", currentTrigger + 1);
        model.save_changes();
      } else {
        stopPolling();
      }
    }, interval);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  function handlePollingActiveChange() {
    updatePollingButton();
    const isActive = model.get("polling_active");
    if (isActive) {
      startPolling();
    } else {
      stopPolling();
    }
  }

  // Listen for specific trait changes
  model.on("change:process_state change:health", updateProcessInfo);
  model.on("change:stdout_lines", updateStdoutLogs);
  model.on("change:stderr_lines", updateStderrLogs);
  model.on("change:polling_active", handlePollingActiveChange);

  // Update process info periodically to refresh uptime, last health check
  const timeUpdateInterval = setInterval(() => {
    updateProcessInfo();
  }, 5000);

  if (model.get("polling_active")) {
    startPolling();
  }

  return () => {
    stopPolling();
    clearInterval(timeUpdateInterval);
  };
}

export default { render };
