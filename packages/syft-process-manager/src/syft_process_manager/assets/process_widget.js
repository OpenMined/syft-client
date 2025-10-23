function render({ model, el }) {
  // Create container
  const container = document.createElement("div");
  container.className = "process-widget";
  el.appendChild(container);

  function updateView() {
    const config = model.get("config");
    const processState = model.get("process_state");
    const health = model.get("health");
    const stdoutLines = model.get("stdout_lines");
    const stderrLines = model.get("stderr_lines");
    const theme = model.get("theme");
    const pollingActive = model.get("polling_active");

    // Derive display values
    const name = config?.name || "Unknown";
    const pid = processState?.pid || null;
    const uptime = calculateUptime(processState?.created_at);
    const status = deriveStatus(processState, health);
    const lastHealthCheck = health?.timestamp
      ? timeAgo(health.timestamp)
      : "never";
    const processDir = config?.process_dir || "-";
    const ttl = config?.ttl_seconds ? `${config.ttl_seconds}s` : "-";

    // Status icons
    const statusIcons = {
      running: "✅",
      unhealthy: "⚠️",
      stopped: "⭕",
      unknown: "❓",
    };
    const statusIcon = statusIcons[status] || statusIcons["unknown"];

    const themeClass = theme === "dark" ? "theme-dark" : "theme-light";

    // Build HTML
    container.innerHTML = `
            <div class="process-widget-container ${themeClass}">
                <div class="process-widget-header">
                    <h3 class="process-widget-title">⚙️ ${name}</h3>
                    <button class="process-widget-polling-btn" data-action="toggle-polling">
                        ${pollingActive ? "⏸ Pause Widget" : "▶️ Resume Widget"}
                    </button>
                </div>

                <table class="process-widget-table">
                    <tr>
                        <td>Status:</td>
                        <td class="process-widget-status ${status}">
                            ${statusIcon} ${status}
                        </td>
                    </tr>
                    <tr>
                        <td>PID:</td>
                        <td>${pid !== null ? pid : "-"}</td>
                    </tr>
                    <tr>
                        <td>Uptime:</td>
                        <td>${uptime || "-"}</td>
                    </tr>
                    <tr>
                        <td>Last Health Report:</td>
                        <td>${lastHealthCheck}</td>
                    </tr>
                    <tr>
                        <td>Process Dir:</td>
                        <td>
                            <a href="file://${processDir}" style="text-decoration: underline; font-size: 11px;">
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
                        <div class="process-widget-log-content log-container">
                            ${
                              stdoutLines && stdoutLines.length > 0
                                ? stdoutLines
                                    .map(
                                      (line) =>
                                        `<span>${escapeHtml(line)}</span>`,
                                    )
                                    .join("<br>")
                                : '<em style="color: #888;">No recent output</em>'
                            }
                        </div>
                    </div>

                    <div class="process-widget-log-panel">
                        <div class="process-widget-log-header">Recent errors:</div>
                        <div class="process-widget-log-content stderr log-container">
                            ${
                              stderrLines && stderrLines.length > 0
                                ? stderrLines
                                    .map(
                                      (line) =>
                                        `<span>${escapeHtml(line)}</span>`,
                                    )
                                    .join("<br>")
                                : '<em style="color: #888;">No recent errors</em>'
                            }
                        </div>
                    </div>
                </div>
            </div>
        `;

    // Auto-scroll log containers to bottom
    const logContainers = container.querySelectorAll(".log-container");
    logContainers.forEach((logContainer) => {
      logContainer.scrollTop = logContainer.scrollHeight;
    });

    // Wire up polling toggle button
    const pollingBtn = container.querySelector(
      '[data-action="toggle-polling"]',
    );
    if (pollingBtn) {
      pollingBtn.onclick = () => {
        model.set("polling_active", !pollingActive);
        model.save_changes();
      };
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

  function calculateUptime(createdAt) {
    if (!createdAt) return null;
    const created = new Date(createdAt);
    const now = new Date();
    const diffSeconds = Math.floor((now - created) / 1000);

    if (diffSeconds < 60) return "< 1m";
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ${diffMinutes % 60}m`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ${diffHours % 24}h`;
  }

  function timeAgo(timestamp) {
    if (!timestamp) return "never";
    const then = new Date(timestamp);
    const now = new Date();
    const diffSeconds = Math.floor((now - then) / 1000);

    if (diffSeconds < 5) return "just now";
    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    const diffMinutes = Math.floor(diffSeconds / 60);
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // Initial render
  updateView();

  // Listen for changes to any trait
  model.on("change", updateView);

  // JavaScript-side polling for Colab compatibility
  // In Colab, Python background threads pause when idle, so we poll from JS
  let pollInterval = null;

  function startPolling() {
    if (pollInterval) return;

    const interval = model.get("polling_interval") * 1000 || 1000;
    console.log(
      `ProcessWidget: Starting JS polling with interval ${interval}ms`,
    );
    pollInterval = setInterval(() => {
      const isActive = model.get("polling_active");
      console.log(`ProcessWidget JS: polling tick, active=${isActive}`);
      if (isActive) {
        // Increment poll trigger to notify Python
        const currentTrigger = model.get("_poll_trigger") || 0;
        console.log(
          `ProcessWidget JS: incrementing _poll_trigger from ${currentTrigger}`,
        );
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

  // Start polling when polling_active is true
  model.on("change:polling_active", () => {
    const isActive = model.get("polling_active");
    if (isActive) {
      startPolling();
    } else {
      stopPolling();
    }
  });

  // Start polling immediately if active
  if (model.get("polling_active")) {
    startPolling();
  }

  // Cleanup on widget removal
  return () => {
    stopPolling();
  };
}

export default { render };
