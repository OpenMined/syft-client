from pydantic import BaseModel
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from syft_client.client import SyftClient


class Colours(BaseModel):
    bg_color: str = "#1e1e1e"
    border_color: str = "#3e3e3e"
    text_color: str = "#e0e0e0"
    label_color: str = "#a0a0a0"
    log_bg: str = "#1a1a1a"
    error_bg: str = "#1a1a1a"
    log_text_color: str = "#9ca3af"
    error_text_color: str = "#ff6b6b"


class LightColours(Colours):
    pass


class DarkColours(Colours):
    bg_color: str = "#1e1e1e"
    border_color = "#3e3e3e"
    text_color: str = "#e0e0e0"
    label_color: str = "#a0a0a0"
    log_bg: str = "#1a1a1a"
    error_bg: str = "#1a1a1a"
    log_text_color: str = "#9ca3af"
    error_text_color: str = "#ff6b6b"


def header_html(email: str, colours: Colours):
    return f"""
        <div style="background: {colours.bg_color}; border: 1px solid {colours.border_color}; border-radius: 5px; padding: 15px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
            <h3 style="margin: 0 0 15px 0; color: {colours.text_color};">📊 Live Server Logs - {email}</h3>
        """


def get_server_html(server_name: str, server, server_id: str, colours: Colours):
    return f"""
<div style="margin-bottom: 20px;">
    <h4 style="color: {colours.text_color}; margin: 0 0 10px 0;">
        {"🚀" if server_name == "Watcher" else "📥" if server_name == "Receiver" else "🏃"} {server_name} 
        <span style="color: {colours.label_color}; font-size: 0.9em;">(port {server.port})</span>
    </h4>
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <div style="padding: 8px; background: {colours.log_bg}; border-radius: 3px; border: 1px solid {colours.border_color};">
            <div style="color: {colours.label_color}; font-size: 11px; margin-bottom: 5px;">stdout:</div>
            <div id="stdout-{server_id}" style="font-size: 11px; color: {colours.log_text_color}; height: 120px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; word-wrap: break-word;">
                <em style="color: #888;">Loading...</em>
            </div>
        </div>
        <div style="padding: 8px; background: {colours.error_bg}; border-radius: 3px; border: 1px solid {colours.border_color};">
            <div style="color: {colours.label_color}; font-size: 11px; margin-bottom: 5px;">stderr:</div>
            <div id="stderr-{server_id}" style="font-size: 11px; color: {colours.error_text_color}; height: 120px; overflow-y: auto; font-family: monospace; white-space: pre-wrap; word-wrap: break-word;">
                <em style="color: #888;">Loading...</em>
            </div>
        </div>
    </div>
</div>
"""


def server_update_js():
    return """
const update_server = async function(server_id, server_port) {{
    const port = server_port;
    const stdoutDiv = document.getElementById('stdout-' + server_id);
    const stderrDiv = document.getElementById('stderr-' + server_id);
    
    if (!stdoutDiv || !stderrDiv) return;
    
    let baseUrl = 'http://localhost:' + port;
    if (window.location.hostname.includes('googleusercontent.com')) {{
        baseUrl = window.location.origin + '/proxy/' + port;
    }}
    
    try {{
        // Fetch stdout
        const stdoutResponse = await fetch(baseUrl + '/logs/stdout?lines=30');
        if (stdoutResponse.ok) {{
            const stdoutData = await stdoutResponse.json();
            if (stdoutData.lines && stdoutData.lines.length > 0) {{
                // Check if we're at the bottom before updating
                const wasAtBottom = stdoutDiv.scrollHeight - stdoutDiv.scrollTop <= stdoutDiv.clientHeight + 5;
                
                stdoutDiv.innerHTML = stdoutData.lines
                    .map(line => line.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
                    .join('');
                
                // Only auto-scroll if we were already at the bottom
                if (wasAtBottom) {{
                    stdoutDiv.scrollTop = stdoutDiv.scrollHeight;
                }}
            }} else {{
                stdoutDiv.innerHTML = '<em style="color: #888;">No output</em>';
            }}
        }}
        
        // Fetch stderr  
        const stderrResponse = await fetch(baseUrl + '/logs/stderr?lines=30');
        if (stderrResponse.ok) {{
            const stderrData = await stderrResponse.json();
            if (stderrData.lines && stderrData.lines.length > 0) {{
                // Check if we're at the bottom before updating
                const wasAtBottom = stderrDiv.scrollHeight - stderrDiv.scrollTop <= stderrDiv.clientHeight + 5;
                
                stderrDiv.innerHTML = stderrData.lines
                    .map(line => line.replace(/</g, '&lt;').replace(/>/g, '&gt;'))
                    .join('');
                
                // Only auto-scroll if we were already at the bottom
                if (wasAtBottom) {{
                    stderrDiv.scrollTop = stderrDiv.scrollHeight;
                }}
            }} else {{
                stderrDiv.innerHTML = '<em style="color: #888;">No errors</em>';
            }}
        }}
    }} catch (error) {{
        // Server might be down
    }}
}};
            """


def get_is_dark_mode():
    try:
        from jupyter_dark_detect import is_dark

        is_dark_mode = is_dark()
    except:
        is_dark_mode = False
    return is_dark_mode


class LogsView:
    def __init__(self, client: "SyftClient"):
        self.client = client

    def update_calls(self, servers, instance_id):
        update_calls = []
        for server_name, server in servers:
            server_id = f"{server_name.lower().replace(' ', '_')}_{instance_id}"
            update_calls.append(f"update_server({server_id}, {server.port});\n")
        return "".join(update_calls)

    def _repr_html_(self):
        """Generate HTML for combined live logs display"""
        # Get all three servers
        servers = []
        if self.client.watcher:
            servers.append(("Watcher", self.client.watcher))
        if self.client.receiver:
            servers.append(("Receiver", self.client.receiver))
        if self.client.job_runner:
            servers.append(("Job Runner", self.client.job_runner))

        if not servers:
            return "<div style='padding: 20px; color: #666;'>No servers running</div>"

        is_dark_mode = get_is_dark_mode()
        # Theme colors
        colours = DarkColours() if is_dark_mode else LightColours

        # Generate unique ID for this instance
        instance_id = str(uuid.uuid4())[:8]

        return f"""
{header_html(self.client.email, colours)}
<script>
(function() {{

    {server_update_js()}
    // Clean up any existing intervals
    const intervalKey = 'syftLogsInterval_' + '{instance_id}';
    if (window[intervalKey]) {{
        clearInterval(window[intervalKey]);
    }}
    
    // Initial update for all servers
    {self.update_calls(servers, instance_id)}
    // Set up polling
    window[intervalKey] = setInterval(function() {{
    {self.update_calls(servers, instance_id)}

    }}, 1000);
}})();
</script>
</div>
"""

    def __repr__(self):
        """Text representation for non-notebook environments"""
        servers_status = []
        if self.client.watcher:
            servers_status.append(f"Watcher: port {self.client.watcher.port}")
        if self.client.receiver:
            servers_status.append(f"Receiver: port {self.client.receiver.port}")
        if self.client.job_runner:
            servers_status.append(f"Job Runner: port {self.client.job_runner.port}")

        if servers_status:
            return f"LogsView({', '.join(servers_status)})"
        else:
            return "LogsView(No servers running)"
