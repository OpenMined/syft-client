"""
Template Renderer: Renders email templates using Jinja2.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape


class TemplateRenderer:
    """Renders Jinja2 templates for email notifications."""

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize the template renderer.

        Args:
            templates_dir: Path to templates directory. Defaults to ./templates
        """
        if templates_dir is None:
            templates_dir = Path(__file__).parent / "templates"

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Add custom filters
        self.env.filters["datetime"] = self._format_datetime
        self.env.filters["duration"] = self._format_duration

    def render(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render a template with the given context.

        Args:
            template_name: Name of template file (e.g., 'emails/new_job.html')
            context: Dictionary of variables to pass to template

        Returns:
            Rendered HTML string
        """
        template = self.env.get_template(template_name)
        return template.render(**context)

    def render_with_fallback(
        self, template_name: str, context: Dict[str, Any], fallback_text: str
    ) -> tuple[str, str]:
        """
        Render template with plain text fallback.

        Args:
            template_name: Name of template file
            context: Dictionary of variables
            fallback_text: Plain text to use if rendering fails

        Returns:
            Tuple of (html_content, plain_text)
        """
        try:
            html = self.render(template_name, context)
            # Generate plain text version from context
            plain = self._generate_plain_text(template_name, context, fallback_text)
            return html, plain
        except Exception:
            return "", fallback_text

    def _generate_plain_text(
        self, template_name: str, context: Dict[str, Any], fallback: str
    ) -> str:
        """
        Generate plain text version of email.

        Tries to render a .txt version of the template, falls back to provided text.
        """
        # Try to find .txt version of template
        txt_template = template_name.replace(".html", ".txt")
        try:
            return self.render(txt_template, context)
        except Exception:
            return fallback

    @staticmethod
    def _format_datetime(dt: datetime) -> str:
        """Format datetime for display in emails."""
        if isinstance(dt, str):
            return dt
        return dt.strftime("%B %d, %Y at %I:%M %p")

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Format duration in human-readable format."""
        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)

        parts = []
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if secs > 0 or not parts:
            parts.append(f"{secs} second{'s' if secs != 1 else ''}")

        return " ".join(parts)
