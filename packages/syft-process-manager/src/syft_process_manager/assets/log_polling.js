(function () {
  const backendUrl = "BACKEND_URL_PLACEHOLDER";
  const stdoutPath = "STDOUT_PATH_PLACEHOLDER";
  const stderrPath = "STDERR_PATH_PLACEHOLDER";
  const instanceId = "INSTANCE_ID_PLACEHOLDER";
  const stdoutDiv = document.getElementById("stdout-" + instanceId);
  const stderrDiv = document.getElementById("stderr-" + instanceId);
  const logTextColor = "LOG_TEXT_COLOR_PLACEHOLDER";
  const errorTextColor = "ERROR_TEXT_COLOR_PLACEHOLDER";

  // Clean up any existing interval for this instance
  const intervalKey = "syftpmInterval_" + instanceId;
  if (window[intervalKey]) {
    clearInterval(window[intervalKey]);
  }

  let errorCount = 0;

  async function updateLogs() {
    try {
      // Fetch stdout
      const stdoutUrl =
        backendUrl +
        "/read_lines?file_path=" +
        encodeURIComponent(stdoutPath) +
        "&mode=tail&num_lines=20";
      const stdoutResponse = await fetch(stdoutUrl);
      if (stdoutResponse.ok) {
        const stdoutData = await stdoutResponse.json();
        if (stdoutData.lines && stdoutData.lines.length > 0) {
          // Check if we're at the bottom before updating
          const wasAtBottom =
            stdoutDiv.scrollHeight - stdoutDiv.scrollTop <=
            stdoutDiv.clientHeight + 5;

          stdoutDiv.innerHTML = stdoutData.lines
            .map((line) => {
              // Strip newlines and escape HTML
              const cleanLine = line
                .replace(/\n$/, "")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");
              return (
                '<span style="color: ' +
                logTextColor +
                '; font-family: monospace;">' +
                cleanLine +
                "</span>"
              );
            })
            .join("<br>");

          // Only auto-scroll if we were already at the bottom
          if (wasAtBottom) {
            stdoutDiv.scrollTop = stdoutDiv.scrollHeight;
          }
        } else {
          stdoutDiv.innerHTML =
            '<em style="color: #888;">No recent output</em>';
        }
        errorCount = 0;
      } else {
        throw new Error("stdout fetch failed: " + stdoutResponse.status);
      }

      // Fetch stderr
      const stderrUrl =
        backendUrl +
        "/read_lines?file_path=" +
        encodeURIComponent(stderrPath) +
        "&mode=tail&num_lines=20";
      const stderrResponse = await fetch(stderrUrl);
      if (stderrResponse.ok) {
        const stderrData = await stderrResponse.json();
        if (stderrData.lines && stderrData.lines.length > 0) {
          // Check if we're at the bottom before updating
          const wasAtBottom =
            stderrDiv.scrollHeight - stderrDiv.scrollTop <=
            stderrDiv.clientHeight + 5;

          stderrDiv.innerHTML = stderrData.lines
            .map((line) => {
              // Strip newlines and escape HTML
              const cleanLine = line
                .replace(/\n$/, "")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;");
              return (
                '<span style="color: ' +
                errorTextColor +
                '; font-family: monospace;">' +
                cleanLine +
                "</span>"
              );
            })
            .join("<br>");

          // Only auto-scroll if we were already at the bottom
          if (wasAtBottom) {
            stderrDiv.scrollTop = stderrDiv.scrollHeight;
          }
        } else {
          stderrDiv.innerHTML =
            '<em style="color: #888;">No recent errors</em>';
        }
      } else {
        throw new Error("stderr fetch failed: " + stderrResponse.status);
      }
    } catch (error) {
      console.error("syft-process-manager log polling error:", error);
      errorCount++;
      if (errorCount > 3) {
        clearInterval(window[intervalKey]);
        stdoutDiv.innerHTML =
          '<em style="color: #888;">Backend disconnected (check console)</em>';
        stderrDiv.innerHTML =
          '<em style="color: #888;">Backend disconnected (check console)</em>';
      }
    }
  }

  // Initial update
  updateLogs();

  // Set up polling
  window[intervalKey] = setInterval(updateLogs, 1000);
})();
