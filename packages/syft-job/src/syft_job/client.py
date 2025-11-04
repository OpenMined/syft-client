import os
import re
import shutil
from pathlib import Path
from typing import List, Optional

import yaml

from .config import SyftJobConfig


class StdoutViewer:
    """A viewer for stdout content with scrollable display in Jupyter notebooks."""

    def __init__(self, job_info: "JobInfo"):
        self.job_info = job_info

    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape sequences from text."""
        # Pattern to match ANSI escape sequences
        ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
        return ansi_escape.sub("", text)

    def _convert_ansi_to_html(self, text: str) -> str:
        """Convert ANSI color codes to HTML spans."""
        # Basic ANSI color code mapping
        ansi_colors = {
            "30": "color: #000000;",  # black
            "31": "color: #cd3131;",  # red
            "32": "color: #00bc00;",  # green
            "33": "color: #e5e510;",  # yellow
            "34": "color: #0451a5;",  # blue
            "35": "color: #bc05bc;",  # magenta
            "36": "color: #0598bc;",  # cyan
            "37": "color: #ffffff;",  # white
            "90": "color: #666666;",  # bright black (gray)
            "91": "color: #f14c4c;",  # bright red
            "92": "color: #23d18b;",  # bright green
            "93": "color: #f5f543;",  # bright yellow
            "94": "color: #3b8eea;",  # bright blue
            "95": "color: #d670d6;",  # bright magenta
            "96": "color: #29b8db;",  # bright cyan
            "97": "color: #ffffff;",  # bright white
            "1": "font-weight: bold;",  # bold
            "0": "",  # reset
        }

        # Replace ANSI codes with HTML
        result = text

        # Handle reset codes first
        result = re.sub(r"\x1b\[0m", "</span>", result)

        # Handle color codes
        for code, style in ansi_colors.items():
            if style:  # Skip empty styles (like reset)
                pattern = rf"\x1b\[{code}m"
                replacement = f'<span style="{style}">'
                result = re.sub(pattern, replacement, result)

        # Handle any remaining unclosed spans by adding a closing span at the end
        if "<span" in result and result.count("<span") > result.count("</span>"):
            result += "</span>"

        return result

    def __str__(self) -> str:
        """Return the stdout content with ANSI codes stripped."""
        if self.job_info.status != "done":
            return "No stdout available - job not completed yet"

        stdout_file = self.job_info.location / "stdout.txt"

        if not stdout_file.exists():
            return "No stdout file found"

        try:
            with open(stdout_file, "r") as f:
                content = f.read()
                return self._strip_ansi_codes(content)
        except Exception as e:
            return f"Error reading stdout file: {e}"

    def __repr__(self) -> str:
        """Return a brief representation."""
        content = str(self)
        if content.startswith("No stdout") or content.startswith("Error"):
            return content

        lines = content.split("\n")
        if len(lines) <= 3:
            return content
        else:
            return f"StdoutViewer({len(lines)} lines, {len(content)} chars)"

    def _repr_html_(self) -> str:
        """HTML representation for Jupyter notebooks with scrollable view."""
        # Get raw content first to check for errors
        if self.job_info.status != "done":
            error_msg = "No stdout available - job not completed yet"
        else:
            stdout_file = self.job_info.location / "stdout.txt"

            if not stdout_file.exists():
                error_msg = "No stdout file found"
            else:
                try:
                    with open(stdout_file, "r") as f:
                        raw_content = f.read()
                    error_msg = None
                except Exception as e:
                    error_msg = f"Error reading stdout file: {e}"

        # If no content or error, show a simple message
        if error_msg:
            return f"""
            <style>
                .syftjob-stdout-empty {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px;
                    background: #f8f9fa;
                    border: 2px dashed #dee2e6;
                    color: #6c757d;
                    font-style: italic;
                }}
            </style>
            <div class="syftjob-stdout-empty">
                📄 {error_msg}
            </div>
            """

        # Convert ANSI codes to HTML for display
        html_content = self._convert_ansi_to_html(raw_content)

        # Escape any remaining HTML characters that aren't our color spans
        # We need to be careful not to escape our intentional HTML
        html_content = (
            html_content.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
        # Don't escape < and > since we want our HTML spans to work

        # Count lines and characters (use clean content for stats)
        clean_content = self._strip_ansi_codes(raw_content)
        lines = clean_content.split("\n")
        char_count = len(clean_content)
        line_count = len(lines)

        return f"""
        <style>
            .syftjob-stdout-container {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                overflow: hidden;
                background: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                max-width: 100%;
                margin: 16px 0;
            }}

            .syftjob-stdout-header {{
                background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%);
                color: white;
                padding: 12px 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-weight: 600;
            }}

            .syftjob-stdout-title {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 14px;
            }}

            .syftjob-stdout-stats {{
                font-size: 12px;
                opacity: 0.9;
                display: flex;
                gap: 16px;
            }}

            .syftjob-stdout-content {{
                background: #f7fafc;
                border: 1px solid #e2e8f0;
                font-family: 'Monaco', 'Menlo', 'SF Mono', monospace;
                font-size: 12px;
                color: #2d3748;
                padding: 16px;
                overflow: auto;
                white-space: pre-wrap;
                word-wrap: break-word;
                max-height: 400px;
                line-height: 1.5;
                margin: 0;
            }}

            .syftjob-stdout-content::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}

            .syftjob-stdout-content::-webkit-scrollbar-track {{
                background: #f1f1f1;
                border-radius: 4px;
            }}

            .syftjob-stdout-content::-webkit-scrollbar-thumb {{
                background: #c1c1c1;
                border-radius: 4px;
            }}

            .syftjob-stdout-content::-webkit-scrollbar-thumb:hover {{
                background: #a1a1a1;
            }}

            /* Dark theme */
            @media (prefers-color-scheme: dark) {{
                .syftjob-stdout-container {{
                    background: #1a202c;
                    border-color: #4a5568;
                }}

                .syftjob-stdout-header {{
                    background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
                }}

                .syftjob-stdout-content {{
                    background: #2d3748;
                    border-color: #4a5568;
                    color: #e2e8f0;
                }}

                .syftjob-stdout-content::-webkit-scrollbar-track {{
                    background: #2d3748;
                }}

                .syftjob-stdout-content::-webkit-scrollbar-thumb {{
                    background: #4a5568;
                }}

                .syftjob-stdout-content::-webkit-scrollbar-thumb:hover {{
                    background: #718096;
                }}
            }}

            /* Jupyter dark theme */
            .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-stdout-container,
            body[data-jp-theme-light="false"] .syftjob-stdout-container {{
                background: #1a202c;
                border-color: #4a5568;
            }}

            .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-stdout-header,
            body[data-jp-theme-light="false"] .syftjob-stdout-header {{
                background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
            }}

            .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-stdout-content,
            body[data-jp-theme-light="false"] .syftjob-stdout-content {{
                background: #2d3748;
                border-color: #4a5568;
                color: #e2e8f0;
            }}
        </style>

        <div class="syftjob-stdout-container">
            <div class="syftjob-stdout-header">
                <div class="syftjob-stdout-title">
                    📄 stdout.txt
                </div>
                <div class="syftjob-stdout-stats">
                    <span>{line_count} lines</span>
                    <span>{char_count:,} chars</span>
                </div>
            </div>
            <pre class="syftjob-stdout-content">{html_content}</pre>
        </div>
        """


class StderrViewer:
    """A viewer for stderr content with scrollable display in Jupyter notebooks."""

    def __init__(self, job_info: "JobInfo"):
        self.job_info = job_info

    def _strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape sequences from text."""
        # Pattern to match ANSI escape sequences
        ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
        return ansi_escape.sub("", text)

    def _convert_ansi_to_html(self, text: str) -> str:
        """Convert ANSI color codes to HTML spans."""
        # Basic ANSI color code mapping
        ansi_colors = {
            "30": "color: #000000;",  # black
            "31": "color: #cd3131;",  # red
            "32": "color: #00bc00;",  # green
            "33": "color: #e5e510;",  # yellow
            "34": "color: #0451a5;",  # blue
            "35": "color: #bc05bc;",  # magenta
            "36": "color: #0598bc;",  # cyan
            "37": "color: #ffffff;",  # white
            "90": "color: #666666;",  # bright black (gray)
            "91": "color: #f14c4c;",  # bright red
            "92": "color: #23d18b;",  # bright green
            "93": "color: #f5f543;",  # bright yellow
            "94": "color: #3b8eea;",  # bright blue
            "95": "color: #d670d6;",  # bright magenta
            "96": "color: #29b8db;",  # bright cyan
            "97": "color: #ffffff;",  # bright white
            "1": "font-weight: bold;",  # bold
            "0": "",  # reset
        }

        # Replace ANSI codes with HTML
        result = text

        # Handle reset codes first
        result = re.sub(r"\x1b\[0m", "</span>", result)

        # Handle color codes
        for code, style in ansi_colors.items():
            if style:  # Skip empty styles (like reset)
                pattern = rf"\x1b\[{code}m"
                replacement = f'<span style="{style}">'
                result = re.sub(pattern, replacement, result)

        # Handle any remaining unclosed spans by adding a closing span at the end
        if "<span" in result and result.count("<span") > result.count("</span>"):
            result += "</span>"

        return result

    def __str__(self) -> str:
        """Return the stderr content with ANSI codes stripped."""
        if self.job_info.status != "done":
            return "No stderr available - job not completed yet"

        stderr_file = self.job_info.location / "stderr.txt"

        if not stderr_file.exists():
            return "No stderr file found"

        try:
            with open(stderr_file, "r") as f:
                content = f.read()
                return self._strip_ansi_codes(content)
        except Exception as e:
            return f"Error reading stderr file: {e}"

    def __repr__(self) -> str:
        """Return a brief representation."""
        content = str(self)
        if content.startswith("No stderr") or content.startswith("Error"):
            return content

        lines = content.split("\n")
        if len(lines) <= 3:
            return content
        else:
            return f"StderrViewer({len(lines)} lines, {len(content)} chars)"

    def _repr_html_(self) -> str:
        """HTML representation for Jupyter notebooks with scrollable view."""
        # Get raw content first to check for errors
        if self.job_info.status != "done":
            error_msg = "No stderr available - job not completed yet"
        else:
            stderr_file = self.job_info.location / "stderr.txt"

            if not stderr_file.exists():
                error_msg = "No stderr file found"
            else:
                try:
                    with open(stderr_file, "r") as f:
                        raw_content = f.read()
                    error_msg = None
                except Exception as e:
                    error_msg = f"Error reading stderr file: {e}"

        # If no content or error, show a simple message
        if error_msg:
            return f"""
            <style>
                .syftjob-stderr-empty {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px;
                    background: #f8f9fa;
                    border: 2px dashed #dee2e6;
                    color: #6c757d;
                    font-style: italic;
                }}
            </style>
            <div class="syftjob-stderr-empty">
                📄 {error_msg}
            </div>
            """

        # Convert ANSI codes to HTML for display
        html_content = self._convert_ansi_to_html(raw_content)

        # Escape any remaining HTML characters that aren't our color spans
        # We need to be careful not to escape our intentional HTML
        html_content = (
            html_content.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )
        # Don't escape < and > since we want our HTML spans to work

        # Count lines and characters (use clean content for stats)
        clean_content = self._strip_ansi_codes(raw_content)
        lines = clean_content.split("\n")
        char_count = len(clean_content)
        line_count = len(lines)

        return f"""
        <style>
            .syftjob-stderr-container {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                overflow: hidden;
                background: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                max-width: 100%;
                margin: 16px 0;
            }}

            .syftjob-stderr-header {{
                background: linear-gradient(135deg, #e53e3e 0%, #c53030 100%);
                color: white;
                padding: 12px 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-weight: 600;
            }}

            .syftjob-stderr-title {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 14px;
            }}

            .syftjob-stderr-stats {{
                font-size: 12px;
                opacity: 0.9;
                display: flex;
                gap: 16px;
            }}

            .syftjob-stderr-content {{
                background: #f7fafc;
                border: 1px solid #e2e8f0;
                font-family: 'Monaco', 'Menlo', 'SF Mono', monospace;
                font-size: 12px;
                color: #2d3748;
                padding: 16px;
                overflow: auto;
                white-space: pre-wrap;
                word-wrap: break-word;
                max-height: 400px;
                line-height: 1.5;
                margin: 0;
            }}

            .syftjob-stderr-content::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}

            .syftjob-stderr-content::-webkit-scrollbar-track {{
                background: #f1f1f1;
                border-radius: 4px;
            }}

            .syftjob-stderr-content::-webkit-scrollbar-thumb {{
                background: #c1c1c1;
                border-radius: 4px;
            }}

            .syftjob-stderr-content::-webkit-scrollbar-thumb:hover {{
                background: #a1a1a1;
            }}

            /* Dark theme */
            @media (prefers-color-scheme: dark) {{
                .syftjob-stderr-container {{
                    background: #1a202c;
                    border-color: #4a5568;
                }}

                .syftjob-stderr-header {{
                    background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
                }}

                .syftjob-stderr-content {{
                    background: #2d3748;
                    border-color: #4a5568;
                    color: #e2e8f0;
                }}

                .syftjob-stderr-content::-webkit-scrollbar-track {{
                    background: #2d3748;
                }}

                .syftjob-stderr-content::-webkit-scrollbar-thumb {{
                    background: #4a5568;
                }}

                .syftjob-stderr-content::-webkit-scrollbar-thumb:hover {{
                    background: #718096;
                }}
            }}

            /* Jupyter dark theme */
            .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-stderr-container,
            body[data-jp-theme-light="false"] .syftjob-stderr-container {{
                background: #1a202c;
                border-color: #4a5568;
            }}

            .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-stderr-header,
            body[data-jp-theme-light="false"] .syftjob-stderr-header {{
                background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
            }}

            .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-stderr-content,
            body[data-jp-theme-light="false"] .syftjob-stderr-content {{
                background: #2d3748;
                border-color: #4a5568;
                color: #e2e8f0;
            }}
        </style>

        <div class="syftjob-stderr-container">
            <div class="syftjob-stderr-header">
                <div class="syftjob-stderr-title">
                    🚨 stderr.txt
                </div>
                <div class="syftjob-stderr-stats">
                    <span>{line_count} lines</span>
                    <span>{char_count:,} chars</span>
                </div>
            </div>
            <pre class="syftjob-stderr-content">{html_content}</pre>
        </div>
        """


class JobInfo:
    """Information about a job with approval capabilities."""

    def __init__(
        self,
        name: str,
        user: str,
        status: str,
        submitted_by: str,
        location: Path,
        config: SyftJobConfig,
        root_email: str,
        submitted_at: Optional[str] = None,
    ):
        self.name = name
        self.user = user
        self.status = status
        self.submitted_by = submitted_by
        self.location = location
        self._config = config
        self._root_email = root_email
        self.submitted_at = submitted_at

    def __str__(self) -> str:
        status_emojis = {"inbox": "📥", "approved": "✅", "done": "🎉"}
        emoji = status_emojis.get(self.status, "❓")
        return f"{emoji} {self.name} ({self.status}) -> {self.user}"

    def __repr__(self) -> str:
        return (
            f"JobInfo(name='{self.name}', user='{self.user}', status='{self.status}')"
        )

    def accept_by_depositing_result(self, path: str) -> Path:
        """
        Accept a job by depositing the result file or folder and creating done marker.

        Args:
            path: Path to the result file or folder to deposit

        Returns:
            Path to the deposited result file or folder in the outputs directory

        Raises:
            ValueError: If job is not in inbox or approved status
            FileNotFoundError: If the result file or folder doesn't exist
        """
        if self.status not in ["inbox", "approved"]:
            raise ValueError(
                f"Job '{self.name}' is not in inbox or approved status (current: {self.status})"
            )

        result_path = Path(path)
        if not result_path.exists():
            raise FileNotFoundError(f"Result path not found: {path}")

        # Create outputs directory in the job directory
        outputs_dir = self.location / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        # Handle both files and folders
        result_name = result_path.name
        destination = outputs_dir / result_name

        if result_path.is_file():
            # Copy file to outputs directory
            shutil.copy2(str(result_path), str(destination))
        elif result_path.is_dir():
            # Copy entire directory to outputs directory
            shutil.copytree(str(result_path), str(destination))
        else:
            raise ValueError(f"Path is neither a file nor a directory: {path}")

        # Create done marker file (this also creates approved marker if not present)
        self._config.create_approved_marker(self.location)
        self._config.create_done_marker(self.location)

        # Update this object's state
        self.status = "done"

        # Show success message with checkmark
        print(
            f"✅ Job '{self.name}' completed successfully! Result deposited at: {destination}"
        )

        return destination

    def approve(self) -> None:
        """
        Approve a job by creating approved marker file.
        Only the admin user can approve jobs in their own folder.

        Raises:
            ValueError: If job is not in inbox status
            PermissionError: If the current user is not authorized to approve jobs
        """
        if self.status != "inbox":
            raise ValueError(
                f"Job '{self.name}' is not in inbox status (current: {self.status})"
            )

        # Only allow admin to approve jobs in their own folder
        if self.user != self._root_email:
            raise PermissionError(
                f"Only the admin user ({self._root_email}) can approve jobs in their folder. "
                f"Current job is in {self.user}'s folder."
            )

        # Create approved marker file
        self._config.create_approved_marker(self.location)

        # Update this object's state
        self.status = "approved"

        # Show success message with checkmark
        print(f"✅ Job '{self.name}' approved successfully!")

    @property
    def output_paths(self) -> List[Path]:
        """
        Get list of all file paths in the outputs directory for done jobs.

        Returns:
            List of Path objects for all files/directories in outputs folder.
            Empty list if job is not done or outputs directory doesn't exist.
        """
        if self.status != "done":
            return []

        outputs_dir = self.location / "outputs"
        if not outputs_dir.exists():
            return []

        try:
            return [item for item in outputs_dir.iterdir()]
        except Exception:
            return []

    @property
    def stdout(self) -> "StdoutViewer":
        """
        Get a viewer for the stdout content from the logs directory for completed jobs.

        Returns:
            StdoutViewer object that displays stdout content in a scrollable view.
        """
        return StdoutViewer(self)

    @property
    def stderr(self) -> "StderrViewer":
        """
        Get a viewer for the stderr content from the logs directory for completed jobs.

        Returns:
            StderrViewer object that displays stderr content in a scrollable view.
        """
        return StderrViewer(self)

    def rerun(self) -> None:
        """
        Rerun a job by removing logs, outputs, and done marker file.
        This makes the job executable again by clearing previous execution artifacts.

        Removes:
        - logs directory (if exists)
        - outputs directory (if exists)
        - done marker file (if exists)

        Raises:
            ValueError: If job is not in done status
        """
        if self.status != "done":
            raise ValueError(
                f"Job '{self.name}' is not in done status (current: {self.status}). "
                f"Only completed jobs can be rerun."
            )

        changes_made = []

        # Remove logs directory if it exists
        logs_dir = self.location / "logs"
        if logs_dir.exists() and logs_dir.is_dir():
            shutil.rmtree(logs_dir)
            changes_made.append("logs directory")

        # Remove outputs directory if it exists
        outputs_dir = self.location / "outputs"
        if outputs_dir.exists() and outputs_dir.is_dir():
            shutil.rmtree(outputs_dir)
            changes_made.append("outputs directory")

        # Remove done marker file if it exists
        done_file = self.location / "done"
        if done_file.exists():
            done_file.unlink()
            changes_made.append("done marker file")

        # Update this object's state - job should now be approved (ready to run)
        self.status = "approved"

        # Show success message
        if changes_made:
            print(
                f"🔄 Job '{self.name}' prepared for rerun! Removed: {', '.join(changes_made)}"
            )
        else:
            print(f"🔄 Job '{self.name}' prepared for rerun! (No cleanup needed)")

    @property
    def files(self) -> List[Path]:
        """
        Get list of all file paths in the job folder.

        Returns:
            List of Path objects for all files and directories in the job folder.
            Empty list if job folder doesn't exist or can't be accessed.
        """
        try:
            if not self.location.exists():
                return []
            return [item for item in self.location.iterdir()]
        except Exception:
            return []

    def _get_python_syntax_highlighted_html(self, code: str) -> str:
        """Convert Python code to syntax-highlighted HTML."""
        # Basic Python syntax highlighting with colors
        # Keywords
        keywords = [
            "and",
            "as",
            "assert",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "exec",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "not",
            "or",
            "pass",
            "print",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
            "True",
            "False",
            "None",
        ]

        # Escape HTML first
        code = (
            code.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )

        # Apply syntax highlighting
        import re

        # Comments (lines starting with #)
        code = re.sub(
            r"(#.*)",
            r'<span style="color: #6a737d; font-style: italic;">\1</span>',
            code,
        )

        # Strings (basic handling for single and double quotes)
        code = re.sub(
            r"(&quot;[^&]*?&quot;)", r'<span style="color: #032f62;">\1</span>', code
        )
        code = re.sub(
            r"(&#x27;[^&]*?&#x27;)", r'<span style="color: #032f62;">\1</span>', code
        )

        # Keywords
        for keyword in keywords:
            code = re.sub(
                rf"\b({keyword})\b",
                r'<span style="color: #d73a49; font-weight: bold;">\1</span>',
                code,
            )

        # Function definitions
        code = re.sub(
            r"\b(def)\s+(\w+)",
            r'<span style="color: #d73a49; font-weight: bold;">\1</span> <span style="color: #6f42c1; font-weight: bold;">\2</span>',
            code,
        )

        # Class definitions
        code = re.sub(
            r"\b(class)\s+(\w+)",
            r'<span style="color: #d73a49; font-weight: bold;">\1</span> <span style="color: #6f42c1; font-weight: bold;">\2</span>',
            code,
        )

        return code

    def _repr_html_(self) -> str:
        """HTML representation for individual job display in Jupyter - matches jobs table styling."""
        # Read job config if available
        submitted_time = "Unknown"
        job_type = "bash"
        try:
            config_file = self.location / "config.yaml"
            if config_file.exists():
                from datetime import datetime

                import yaml

                with open(config_file, "r") as f:
                    config_data = yaml.safe_load(f)
                    job_type = config_data.get("type", "bash")
                    submitted_at = config_data.get("submitted_at")

                    if submitted_at:
                        # Parse ISO format timestamp
                        try:
                            dt = datetime.fromisoformat(
                                submitted_at.replace("Z", "+00:00")
                            )
                            submitted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            submitted_time = str(submitted_at)
                    else:
                        # Fallback to file modification time
                        import os

                        mtime = os.path.getmtime(config_file)
                        dt = datetime.fromtimestamp(mtime)
                        submitted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                # If no config file, use job directory modification time
                import os

                if self.location.exists():
                    mtime = os.path.getmtime(self.location)
                    dt = datetime.fromtimestamp(mtime)
                    submitted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            submitted_time = "Unknown"

        # Read job script if available
        script_content = "No script available"
        try:
            script_file = self.location / "run.sh"
            if script_file.exists():
                with open(script_file, "r") as f:
                    script_content = f.read().strip()
                    # If content is too long, truncate and add ellipsis
                    if len(script_content) > 500:
                        script_content = script_content[:500] + "..."
                    # Escape HTML characters
                    script_content = (
                        script_content.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                        .replace('"', "&quot;")
                        .replace("'", "&#x27;")
                    )
        except Exception:
            pass

        # Generate Code section for Python jobs
        code_section = ""
        if job_type == "python":
            try:
                # Find Python files in the job directory
                python_files = [
                    f
                    for f in self.location.iterdir()
                    if f.suffix == ".py" and f.is_file()
                ]
                if python_files:
                    # Use the first Python file found
                    py_file = python_files[0]
                    with open(py_file, "r") as f:
                        py_content = f.read()

                    # Apply syntax highlighting
                    highlighted_content = self._get_python_syntax_highlighted_html(
                        py_content
                    )

                    code_section = f"""
                <div class="syftjob-single-section">
                    <h4>🐍 Code</h4>
                    <div class="syftjob-single-filename">{py_file.name}</div>
                    <div class="syftjob-single-code">{highlighted_content}</div>
                </div>"""
            except Exception:
                pass

        # Generate outputs section for done jobs
        outputs_section = ""
        if self.status == "done":
            output_files = self.output_paths
            if output_files:
                outputs_items = "\n".join(
                    [
                        f'                        <div class="syftjob-single-outputs-item">📄 {path.name}</div>'
                        for path in output_files
                    ]
                )
                outputs_section = f"""
                <div class="syftjob-single-section">
                    <h4>📁 Outputs ({len(output_files)} files)</h4>
                    <div class="syftjob-single-outputs-list">
{outputs_items}
                    </div>
                </div>"""

        return f"""
        <style>
            .syftjob-single {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                border: 2px solid #9CA3AF;
                margin: 16px 0;
                background: white;
                font-size: 14px;
                max-width: 100%;
            }}

            .syftjob-single-header {{
                background: #1F2937;
                color: white;
                padding: 12px 16px;
                border-bottom: 2px solid #111827;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}

            .syftjob-single-title {{
                display: flex;
                align-items: center;
                gap: 12px;
                font-size: 16px;
                font-weight: 700;
                margin: 0;
            }}

            .syftjob-single-status-inbox {{
                background: #FBBF24;
                color: #451A03;
                padding: 4px 8px;
                border: 2px solid #B45309;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 700;
                display: inline-block;
            }}

            .syftjob-single-status-approved {{
                background: #60A5FA;
                color: #1E3A8A;
                padding: 4px 8px;
                border: 2px solid #1D4ED8;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 700;
                display: inline-block;
            }}

            .syftjob-single-status-done {{
                background: #34D399;
                color: #064E3B;
                padding: 4px 8px;
                border: 2px solid #047857;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 700;
                display: inline-block;
            }}

            .syftjob-single-content {{
                padding: 16px;
                background: white;
            }}

            .syftjob-single-details {{
                display: grid;
                gap: 12px;
                margin-bottom: 16px;
            }}

            .syftjob-single-detail {{
                display: flex;
                align-items: flex-start;
                gap: 12px;
                padding: 8px;
                background: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 4px;
            }}

            .syftjob-single-detail-label {{
                color: #374151;
                font-weight: 700;
                min-width: 120px;
                font-size: 13px;
            }}

            .syftjob-single-detail-value {{
                color: #111827;
                font-size: 13px;
                flex: 1;
            }}

            .syftjob-single-section {{
                margin-top: 20px;
                border: 2px solid #E5E7EB;
                border-radius: 4px;
                overflow: hidden;
            }}

            .syftjob-single-section h4 {{
                background: #F3F4F6;
                margin: 0;
                padding: 8px 12px;
                font-size: 14px;
                color: #111827;
                font-weight: 700;
                border-bottom: 2px solid #E5E7EB;
            }}

            .syftjob-single-script {{
                background: #f8f9fa;
                padding: 12px;
                font-family: 'Monaco', 'Menlo', 'SF Mono', monospace;
                font-size: 12px;
                color: #2d3748;
                overflow: auto;
                white-space: pre-wrap;
                word-wrap: break-word;
                max-height: 200px;
                line-height: 1.4;
                margin: 0;
            }}

            .syftjob-single-filename {{
                background: #E5E7EB;
                padding: 6px 12px;
                font-family: 'Monaco', 'Menlo', 'SF Mono', monospace;
                font-size: 11px;
                color: #374151;
                font-weight: 600;
                border-bottom: 1px solid #D1D5DB;
            }}

            .syftjob-single-code {{
                background: #f8f9fa;
                padding: 16px;
                font-family: 'Monaco', 'Menlo', 'SF Mono', monospace;
                font-size: 12px;
                color: #2d3748;
                overflow: auto;
                white-space: pre-wrap;
                word-wrap: break-word;
                max-height: 400px;
                line-height: 1.5;
                margin: 0;
            }}

            .syftjob-single-outputs-list {{
                padding: 12px;
                background: white;
            }}

            .syftjob-single-outputs-item {{
                padding: 4px 0;
                font-family: 'Monaco', 'Menlo', monospace;
                font-size: 12px;
                color: #4a5568;
            }}

            .syftjob-single-code::-webkit-scrollbar,
            .syftjob-single-script::-webkit-scrollbar {{
                width: 8px;
                height: 8px;
            }}

            .syftjob-single-code::-webkit-scrollbar-track,
            .syftjob-single-script::-webkit-scrollbar-track {{
                background: #f1f1f1;
                border-radius: 4px;
            }}

            .syftjob-single-code::-webkit-scrollbar-thumb,
            .syftjob-single-script::-webkit-scrollbar-thumb {{
                background: #c1c1c1;
                border-radius: 4px;
            }}

            .syftjob-single-code::-webkit-scrollbar-thumb:hover,
            .syftjob-single-script::-webkit-scrollbar-thumb:hover {{
                background: #a1a1a1;
            }}

        </style>
        <div class="syftjob-single">
            <div class="syftjob-single-header">
                <h3 class="syftjob-single-title">📋 {self.name}</h3>
                <span class="syftjob-single-status-{self.status}">
                    {"📥" if self.status == "inbox" else "✅" if self.status == "approved" else "🎉"} {self.status.upper()}
                </span>
            </div>
            <div class="syftjob-single-content">
                <div class="syftjob-single-details">
                    <div class="syftjob-single-detail">
                        <div class="syftjob-single-detail-label">User:</div>
                        <div class="syftjob-single-detail-value">{self.user}</div>
                    </div>
                    <div class="syftjob-single-detail">
                        <div class="syftjob-single-detail-label">Submitted by:</div>
                        <div class="syftjob-single-detail-value">{self.submitted_by}</div>
                    </div>
                    <div class="syftjob-single-detail">
                        <div class="syftjob-single-detail-label">Location:</div>
                        <div class="syftjob-single-detail-value">{self.location}</div>
                    </div>
                    <div class="syftjob-single-detail">
                        <div class="syftjob-single-detail-label">Submitted:</div>
                        <div class="syftjob-single-detail-value">{submitted_time}</div>
                    </div>
                </div>
                <div class="syftjob-single-section">
                    <h4>📜 Script</h4>
                    <div class="syftjob-single-script">{script_content}</div>
                </div>{code_section}{outputs_section}
            </div>
        </div>
        """


class JobsList:
    """A list-like container for JobInfo objects with nice display."""

    def __init__(self, jobs: List[JobInfo], root_email: str):
        self._jobs = jobs
        self._root_email = root_email

    def __getitem__(self, index) -> JobInfo:
        return self._jobs[index]

    def __len__(self) -> int:
        return len(self._jobs)

    def __iter__(self):
        return iter(self._jobs)

    def __str__(self) -> str:
        """Format jobs list as separate tables grouped by user."""
        if not self._jobs:
            return "📭 No jobs found.\n"

        # Group jobs by user
        jobs_by_user: dict[str, list[JobInfo]] = {}
        for job in self._jobs:
            if job.user not in jobs_by_user:
                jobs_by_user[job.user] = []
            jobs_by_user[job.user].append(job)

        # Status emojis
        status_emojis = {"inbox": "📥", "approved": "✅", "done": "🎉"}

        lines = []
        lines.append("📊 Jobs Overview")
        lines.append("=" * 50)

        total_jobs = 0
        global_status_counts: dict[str, int] = {}

        # Sort users with root user first, then alphabetically
        def user_sort_key(item):
            user_email, user_jobs = item
            if user_email == self._root_email:
                return (0, user_email)  # Root user comes first
            return (1, user_email)  # Others sorted alphabetically

        sorted_users = sorted(jobs_by_user.items(), key=user_sort_key)

        # Create a global job index that matches HTML display
        job_index = 0

        # Create a table for each user that has jobs
        for user_email, user_jobs in sorted_users:
            if not user_jobs:  # Skip users with no jobs
                continue

            total_jobs += len(user_jobs)

            lines.append("")
            lines.append(f"👤 {user_email}")
            lines.append("-" * 60)

            # Calculate column widths for this user's jobs
            name_width = max(len(job.name) for job in user_jobs) + 2
            status_width = max(len(job.status) for job in user_jobs) + 2
            submitted_width = max(len(job.submitted_by) for job in user_jobs) + 2

            # Ensure minimum widths
            name_width = max(name_width, 15)
            status_width = max(status_width, 12)
            submitted_width = max(submitted_width, 15)

            # Header
            header = f"{'Index':<6} {'Job Name':<{name_width}} {'Submitted By':<{submitted_width}} {'Status':<{status_width}}"
            lines.append(header)
            lines.append("-" * len(header))

            # Jobs are already sorted by submission time globally, preserve that order
            sorted_jobs = user_jobs

            # Job rows with global indexing
            for job in sorted_jobs:
                emoji = status_emojis.get(job.status, "❓")
                status_display = f"{emoji} {job.status}"
                line = f"[{job_index:<4}] {job.name:<{name_width}} {job.submitted_by:<{submitted_width}} {status_display:<{status_width}}"
                lines.append(line)
                job_index += 1

                # Count for global summary
                global_status_counts[job.status] = (
                    global_status_counts.get(job.status, 0) + 1
                )

            # User summary
            user_status_counts: dict[str, int] = {}
            for job in user_jobs:
                user_status_counts[job.status] = (
                    user_status_counts.get(job.status, 0) + 1
                )

            summary_parts = []
            for status, count in user_status_counts.items():
                emoji = status_emojis.get(status, "❓")
                summary_parts.append(f"{emoji} {count} {status}")

            lines.append(
                f"📋 {user_email}: {len(user_jobs)} jobs - " + " | ".join(summary_parts)
            )

        # Global summary
        lines.append("")
        lines.append("=" * 50)
        lines.append(f"📈 Total: {total_jobs} jobs across {len(jobs_by_user)} users")

        global_summary_parts = []
        for status, count in global_status_counts.items():
            emoji = status_emojis.get(status, "❓")
            global_summary_parts.append(f"{emoji} {count} {status}")

        if global_summary_parts:
            lines.append("📋 Global: " + " | ".join(global_summary_parts))

        lines.append("")
        lines.append(
            "💡 Use job_client.jobs[0].approve() to approve jobs or job_client.jobs[0].accept_by_depositing_result('file_or_folder') to complete jobs"
        )

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"JobsList({len(self._jobs)} jobs)"

    def _repr_html_(self) -> str:
        """HTML representation for Jupyter notebooks with enhanced visual appeal."""
        if not self._jobs:
            return """
            <style>

                .syftjob-empty {
                    padding: 30px 20px;
                    text-align: center;
                    border-radius: 8px;
                    background: linear-gradient(135deg, #f8c073 0%, #f79763 50%, #cc677b 100%);
                    border: 1px solid rgba(248,192,115,0.2);
                    color: white;
                }


                .syftjob-empty h3 {
                    margin: 0 0 12px 0;
                    font-size: 18px;
                    color: white;
                    font-weight: 600;
                }

                .syftjob-empty p {
                    margin: 0;
                    color: rgba(255,255,255,0.9);
                    font-size: 16px;
                    opacity: 0.95;
                }

                .syftjob-empty-icon {
                    font-size: 24px;
                    margin-bottom: 12px;
                    display: block;
                }

                /* Dark theme */
                @media (prefers-color-scheme: dark) {
                    .syftjob-empty {
                        background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
                        border-color: rgba(74,85,104,0.2);
                    }
                    .syftjob-empty h3 {
                        color: white;
                    }
                    .syftjob-empty p {
                        color: rgba(255,255,255,0.95);
                        opacity: 0.95;
                    }
                }

                /* Jupyter dark theme detection */
                .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-empty,
                body[data-jp-theme-light="false"] .syftjob-empty {
                    background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
                    border-color: rgba(74,85,104,0.2);
                }
                .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-empty h3,
                body[data-jp-theme-light="false"] .syftjob-empty h3 {
                    color: white;
                }
                .jp-RenderedHTMLCommon[data-jp-theme-light="false"] .syftjob-empty p,
                body[data-jp-theme-light="false"] .syftjob-empty p {
                    color: rgba(255,255,255,0.95);
                    opacity: 0.95;
                }
            </style>
            <div class="syftjob-empty">
                <span class="syftjob-empty-icon">📭</span>
                <h3>No jobs found</h3>
                <p>Submit jobs to see them here</p>
            </div>
            """

        # Group jobs by user
        jobs_by_user: dict[str, list[JobInfo]] = {}
        for job in self._jobs:
            if job.user not in jobs_by_user:
                jobs_by_user[job.user] = []
            jobs_by_user[job.user].append(job)

        # Status styling for light and dark themes
        status_styles = {
            "inbox": {
                "emoji": "📥",
                "light": {"color": "#6976ae", "bg": "#e8f2ff"},
                "dark": {"color": "#96d195", "bg": "#52a8c5"},
            },
            "approved": {
                "emoji": "✅",
                "light": {"color": "#53bea9", "bg": "#e6f9f4"},
                "dark": {"color": "#53bea9", "bg": "#2a5d52"},
            },
            "done": {
                "emoji": "🎉",
                "light": {"color": "#937098", "bg": "#f3e5f5"},
                "dark": {"color": "#f2d98c", "bg": "#cc677b"},
            },
        }

        # Calculate total counts for summary
        total_jobs = len(self._jobs)
        global_status_counts: dict[str, int] = {}
        for job in self._jobs:
            global_status_counts[job.status] = (
                global_status_counts.get(job.status, 0) + 1
            )

        # Build HTML with clean Excel-like interface
        html = f"""
        <style>
            .syftjob-overview {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 16px 0;
                font-size: 14px;
            }}

            .syftjob-global-header {{
                background: #1F2937;
                color: white;
                padding: 12px 16px;
                border: 2px solid #111827;
                text-align: center;
                margin-bottom: 16px;
            }}

            .syftjob-global-header h3 {{
                margin: 0 0 4px 0;
                font-size: 16px;
                font-weight: 700;
            }}
            .syftjob-global-header p {{
                margin: 0;
                font-size: 13px;
                font-weight: 500;
            }}

            .syftjob-user-section {{
                margin-bottom: 24px;
                border: 2px solid #9CA3AF;
            }}

            .syftjob-user-header {{
                background: #F3F4F6;
                border-bottom: 2px solid #9CA3AF;
                padding: 8px 12px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}

            .syftjob-user-header h4 {{
                margin: 0;
                font-size: 14px;
                font-weight: 700;
                color: #111827;
            }}

            .syftjob-user-summary {{
                font-size: 12px;
                color: #374151;
                font-weight: 600;
            }}

            .syftjob-table {{
                width: 100%;
                border-collapse: collapse;
                background: white;
                font-size: 13px;
                border: 2px solid #6B7280;
            }}

            .syftjob-thead {{
                background: #E5E7EB;
            }}
            .syftjob-th {{
                padding: 8px 12px;
                text-align: left;
                font-weight: 700;
                color: #111827;
                border-right: 2px solid #6B7280;
                border-bottom: 2px solid #6B7280;
            }}
            .syftjob-th:last-child {{ border-right: none; }}

            .syftjob-row-even {{
                background: #FFFFFF;
            }}
            .syftjob-row-odd {{
                background: #F9FAFB;
            }}
            .syftjob-row {{
                border-bottom: 1px solid #9CA3AF;
            }}
            .syftjob-row:hover {{
                background: #DBEAFE !important;
            }}

            .syftjob-td {{
                padding: 8px 12px;
                border-right: 1px solid #9CA3AF;
                vertical-align: middle;
            }}
            .syftjob-td:last-child {{ border-right: none; }}

            .syftjob-index {{
                background: #D1D5DB;
                padding: 4px 8px;
                border-radius: 3px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                font-weight: 700;
                color: #111827;
                border: 2px solid #6B7280;
                display: inline-block;
                min-width: 24px;
                text-align: center;
            }}

            .syftjob-job-name {{
                font-weight: 600;
                color: #111827;
            }}

            .syftjob-status-inbox {{
                background: #FBBF24;
                color: #451A03;
                padding: 3px 8px;
                border: 2px solid #B45309;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 700;
                display: inline-block;
            }}

            .syftjob-status-approved {{
                background: #60A5FA;
                color: #1E3A8A;
                padding: 3px 8px;
                border: 2px solid #1D4ED8;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 700;
                display: inline-block;
            }}

            .syftjob-status-done {{
                background: #34D399;
                color: #064E3B;
                padding: 3px 8px;
                border: 2px solid #047857;
                border-radius: 3px;
                font-size: 11px;
                font-weight: 700;
                display: inline-block;
            }}

            .syftjob-submitted {{
                color: #374151;
                font-size: 12px;
                font-weight: 600;
            }}

            .syftjob-global-footer {{
                background: #F3F4F6;
                padding: 12px 16px;
                text-align: center;
                border: 2px solid #9CA3AF;
                margin-top: 16px;
            }}

            .syftjob-global-summary {{
                display: flex;
                justify-content: center;
                gap: 16px;
                margin-bottom: 12px;
                flex-wrap: wrap;
            }}

            .syftjob-summary-item {{
                display: inline-block;
                font-size: 12px;
                color: #111827;
                padding: 4px 8px;
                background: white;
                border: 2px solid #6B7280;
                border-radius: 3px;
                font-weight: 600;
            }}

            .syftjob-hint {{
                font-size: 12px;
                color: #374151;
                line-height: 1.4;
                margin-top: 8px;
                font-weight: 500;
            }}

            .syftjob-code {{
                background: #E5E7EB;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: 2px solid #6B7280;
                font-weight: 600;
                color: #111827;
            }}

        </style>

        <div class="syftjob-overview">
            <div class="syftjob-global-header">
                <h3>📊 Jobs Overview</h3>
                <p>Total: {total_jobs} jobs across {len(jobs_by_user)} users</p>
            </div>
        """

        # Create a separate table for each user that has jobs
        # Sort users with root user first, then alphabetically
        def user_sort_key(item):
            user_email, user_jobs = item
            if user_email == self._root_email:
                return (0, user_email)  # Root user comes first
            return (1, user_email)  # Others sorted alphabetically

        sorted_users = sorted(jobs_by_user.items(), key=user_sort_key)

        job_index = 0
        for user_email, user_jobs in sorted_users:
            if not user_jobs:  # Skip users with no jobs
                continue

            # Jobs are already sorted by submission time globally, preserve that order
            sorted_user_jobs = user_jobs

            # Calculate user summary
            user_status_counts: dict[str, int] = {}
            for job in user_jobs:
                user_status_counts[job.status] = (
                    user_status_counts.get(job.status, 0) + 1
                )

            user_summary_parts = []
            for status, count in user_status_counts.items():
                emoji = status_styles.get(status, {}).get("emoji", "❓")
                user_summary_parts.append(f"{emoji} {count} {status}")

            html += f"""
            <div class="syftjob-user-section">
                <div class="syftjob-user-header">
                    <h4>👤 {user_email}</h4>
                    <div class="syftjob-user-summary">{len(user_jobs)} jobs - {" | ".join(user_summary_parts)}</div>
                </div>
                <table class="syftjob-table">
                    <thead class="syftjob-thead">
                        <tr>
                            <th class="syftjob-th">Index</th>
                            <th class="syftjob-th">Job Name</th>
                            <th class="syftjob-th">Submitted By</th>
                            <th class="syftjob-th">Status</th>
                        </tr>
                    </thead>
                    <tbody>
            """

            # Add job rows for this user
            for i, job in enumerate(sorted_user_jobs):
                style_info = status_styles.get(job.status, {"emoji": "❓"})
                row_class = "syftjob-row-even" if i % 2 == 0 else "syftjob-row-odd"

                html += f"""
                        <tr class="{row_class} syftjob-row">
                            <td class="syftjob-td">
                                <span class="syftjob-index">[{job_index}]</span>
                            </td>
                            <td class="syftjob-td syftjob-job-name">
                                {job.name}
                            </td>
                            <td class="syftjob-td syftjob-submitted">
                                {job.submitted_by}
                            </td>
                            <td class="syftjob-td">
                                <span class="syftjob-status-{job.status}">
                                    {style_info["emoji"]} {job.status.upper()}
                                </span>
                            </td>
                        </tr>
                """
                job_index += 1

            html += """
                    </tbody>
                </table>
            </div>
            """

        # Add global summary footer
        html += """
            <div class="syftjob-global-footer">
                <div class="syftjob-global-summary">
        """

        for status, count in global_status_counts.items():
            style_info = status_styles.get(status, {"emoji": "❓"})
            html += f"""
                    <span class="syftjob-summary-item">
                        {style_info["emoji"]} {count} {status}
                    </span>
            """

        html += """
                </div>
                <div class="syftjob-hint">
                    💡 Use <code class="syftjob-code">jobs[0].approve()</code> to approve jobs or <code class="syftjob-code">jobs[0].accept_by_depositing_result('file_or_folder')</code> to complete jobs
                </div>
            </div>
        </div>
        """

        return html


class JobClient:
    """Client for submitting jobs to SyftBox."""

    def __init__(self, config: SyftJobConfig, user_email: Optional[str] = None):
        """Initialize JobClient with configuration and optional user email for job views."""
        self.config = config
        self.root_email = config.email  # From SyftBox folder (for "submitted_by")
        self.user_email = user_email or config.email  # Target user for job views

        # Validate that user_email exists in SyftBox root
        self._validate_user_email()

    @classmethod
    def from_config(cls, config: SyftJobConfig) -> "JobClient":
        return cls(config, config.email)

    def _validate_user_email(self) -> None:
        """Validate that the user_email directory exists in SyftBox root."""
        user_dir = self.config.get_user_dir(self.user_email)
        if not user_dir.exists():
            # Create user directory if it doesn't exist
            user_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created user directory: {user_dir}")

    def _ensure_job_directories(self, user_email: str) -> None:
        """Ensure job directory structure exists for a user."""
        job_dir = self.config.get_job_dir(user_email)

        # Create job directory if it doesn't exist
        job_dir.mkdir(parents=True, exist_ok=True)

    def submit_bash_job(self, user: str, script: str, job_name: str = "") -> Path:
        """
        Submit a bash job for a user.

        Args:
            user: Email address of the user to submit job for
            script: Bash script content to execute
            job_name: Name of the job (will be used as directory name). If empty, defaults to "Job - <random_id>"

        Returns:
            Path to the created job directory

        Raises:
            FileExistsError: If job with same name already exists
            ValueError: If user directory doesn't exist
        """
        # Generate default job name if not provided
        if not job_name.strip():
            from uuid import uuid4

            random_id = str(uuid4())[0:8]
            job_name = f"Job - {random_id}"
        # Ensure user directory exists (create if it doesn't)
        user_dir = self.config.get_user_dir(user)
        if not user_dir.exists():
            user_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created user directory: {user_dir}")

        # Ensure job directory structure exists
        self._ensure_job_directories(user)

        # Create job directory directly in job directory
        job_dir = self.config.get_job_dir(user) / job_name

        if job_dir.exists():
            raise FileExistsError(f"Job '{job_name}' already exists for user '{user}'")

        job_dir.mkdir(parents=True)

        # Create run.sh file
        run_script_path = job_dir / "run.sh"
        with open(run_script_path, "w") as f:
            f.write(script)

        # Make run.sh executable
        os.chmod(run_script_path, 0o755)

        # Create config.yaml file
        config_yaml_path = job_dir / "config.yaml"
        from datetime import datetime, timezone

        job_config = {
            "name": job_name,
            "submitted_by": self.root_email,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(config_yaml_path, "w") as f:
            yaml.dump(job_config, f, default_flow_style=False)

        return job_dir

    def submit_python_job(
        self,
        user: str,
        code_path: str,
        job_name: Optional[str] = "",
        dependencies: Optional[List[str]] = None,
    ) -> Path:
        """
        Submit a Python job for a user (single file only).

        Args:
            user: Email address of the user to submit job for
            job_name: Name of the job (will be used as directory name)
            code_path: Path to Python file (folders are temporarily disabled)
            dependencies: List of Python packages to install (e.g., ["numpy", "pandas==1.5.0"])

        Returns:
            Path to the created job directory

        Raises:
            FileExistsError: If job with same name already exists
            ValueError: If code_path is not a single Python file
            FileNotFoundError: If code_path doesn't exist
        """
        # Generate default job name if not provided
        if not job_name:
            from uuid import uuid4

            random_id = str(uuid4())[0:8]
            job_name = f"Job - {random_id}"

        # Validate code_path exists
        code_path_obj = Path(code_path).expanduser().resolve()
        if not code_path_obj.exists():
            raise FileNotFoundError(f"Code path does not exist: {code_path}")

        # Only accept single Python files (folders temporarily disabled)
        if not code_path_obj.is_file():
            raise ValueError(
                f"Code path must be a single Python file. Folders are temporarily disabled: {code_path}"
            )

        if not code_path_obj.suffix == ".py":
            raise ValueError(f"Code path must be a Python file (.py): {code_path}")

        # Ensure user directory exists (create if it doesn't)
        user_dir = self.config.get_user_dir(user)
        if not user_dir.exists():
            user_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created user directory: {user_dir}")

        # Ensure job directory structure exists
        self._ensure_job_directories(user)

        # Create job directory directly in job directory
        job_dir = self.config.get_job_dir(user) / job_name

        if job_dir.exists():
            raise FileExistsError(f"Job '{job_name}' already exists for user '{user}'")

        job_dir.mkdir(parents=True)

        # Copy Python file directly to job root directory
        destination = job_dir / code_path_obj.name
        shutil.copy2(str(code_path_obj), str(destination))

        # Generate bash script for Python execution with uv
        dependencies = dependencies or []

        # Always include syft-client as a default dependency
        all_dependencies = ["syft-client"] + dependencies

        # Create dependency installation commands
        deps_str = " ".join(f'"{dep}"' for dep in all_dependencies)
        install_commands = f"""
# Install syft-client and custom dependencies
uv pip install {deps_str}
"""

        bash_script = f"""#!/bin/bash
export UV_SYSTEM_PYTHON=false

# Create isolated uv virtual environment
uv venv

# Activate the virtual environment
source .venv/bin/activate
{install_commands}
# Execute the Python file directly from job root
python {code_path_obj.name}
"""

        # Create run.sh file
        run_script_path = job_dir / "run.sh"
        with open(run_script_path, "w") as f:
            f.write(bash_script)

        # Make run.sh executable
        os.chmod(run_script_path, 0o755)

        # Create config.yaml file
        config_yaml_path = job_dir / "config.yaml"
        from datetime import datetime, timezone

        job_config = {
            "name": job_name,
            "submitted_by": self.root_email,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "type": "python",
            "code_path": str(code_path_obj),
            "entry_point": code_path_obj.name,
            "dependencies": all_dependencies,
        }

        with open(config_yaml_path, "w") as f:
            yaml.dump(job_config, f, default_flow_style=False)

        return job_dir

    def _get_all_jobs(self) -> List[JobInfo]:
        """Get all jobs from all peer directories (inbox, approved, done)."""
        jobs: list[JobInfo] = []
        syftbox_root = self.config.syftbox_folder

        if not syftbox_root.exists():
            return jobs

        # Scan through all user directories in SyftBox root (peers)
        for user_dir in syftbox_root.iterdir():
            if not user_dir.is_dir():
                continue

            user_email = user_dir.name
            user_job_dir = self.config.get_job_dir(user_email)

            if not user_job_dir.exists():
                continue

            # Scan for job directories directly in the job directory
            for job_dir in user_job_dir.iterdir():
                if not job_dir.is_dir():
                    continue

                config_file = job_dir / "config.yaml"
                if not config_file.exists():
                    continue

                try:
                    with open(config_file, "r") as f:
                        job_config = yaml.safe_load(f)

                    # Determine status from marker files
                    status = self.config.get_job_status(job_dir)

                    # Include all jobs from all peer directories
                    jobs.append(
                        JobInfo(
                            name=job_config.get("name", job_dir.name),
                            user=user_email,
                            status=status,
                            submitted_by=job_config.get("submitted_by", "unknown"),
                            location=job_dir,
                            config=self.config,
                            root_email=self.root_email,
                            submitted_at=job_config.get("submitted_at"),
                        )
                    )
                except Exception:
                    # Skip jobs with invalid config files
                    continue

        return jobs

    @property
    def jobs(self) -> JobsList:
        """
        Get all jobs from all peer directories as an indexable list grouped by user.

        Returns a JobsList object that can be:
        - Indexed: jobs[0], jobs[1], etc.
        - Iterated: for job in jobs
        - Displayed: print(jobs) shows separate tables for each user
        - HTML display: in Jupyter, shows separate tables for each user with jobs

        Each job has an accept_by_depositing_result() method for approval.
        Only displays users that have jobs (skips empty peer directories).

        Returns:
            JobsList containing all jobs from all peer directories, grouped by user
        """
        current_jobs = self._get_all_jobs()

        # Sort jobs by recent submissions first (newest first), then by user/status
        def job_sort_key(job):
            # Parse submitted_at timestamp for sorting (most recent first)
            try:
                if job.submitted_at:
                    from datetime import datetime

                    # Parse ISO format timestamp
                    dt = datetime.fromisoformat(job.submitted_at.replace("Z", "+00:00"))
                    # Use negative timestamp for reverse chronological order (newest first)
                    time_priority = -dt.timestamp()
                else:
                    # Jobs without submitted_at go to the end
                    time_priority = float("inf")
            except Exception:
                # Invalid timestamps go to the end
                time_priority = float("inf")

            # Secondary sorting: user priority (root first), then user name, then status
            user_priority = 0 if job.user == self.root_email else 1
            status_priority = {"inbox": 1, "approved": 2, "done": 3}.get(job.status, 4)

            return (
                time_priority,
                user_priority,
                job.user,
                status_priority,
                job.name.lower(),
            )

        sorted_jobs = sorted(current_jobs, key=job_sort_key)
        return JobsList(sorted_jobs, self.user_email)


def get_client(
    syftbox_folder_path: str, email: str, user_email: Optional[str] = None
) -> JobClient:
    """
    Factory function to create a JobClient from SyftBox folder.

    Args:
        syftbox_folder_path: Path to the SyftBox folder
        email: Root user email address (explicit, no inference from folder name)
        user_email: Optional target user email for job views (defaults to root email)

    Returns:
        Configured JobClient instance
    """
    config = SyftJobConfig.from_syftbox_folder(syftbox_folder_path, email)
    return JobClient(config, user_email)
