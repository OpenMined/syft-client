"""Reusable Rich-based UI components for notebook authentication."""

from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)


class RichComponents:
    """Rich-based component helpers for authentication UI."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize with optional console."""
        self.console = console or Console()

    def display_panel(
        self,
        content: str,
        title: str,
        border_style: str = "blue",
    ):
        """
        Display a styled panel.

        Args:
            content: Panel content (supports Rich markup)
            title: Panel title
            border_style: Border color/style
        """
        self.console.print(
            Panel(content, title=title, border_style=border_style, title_align="left")
        )
        self.console.print()  # Add spacing

    def display_status(self, message: str, status_type: str = "info", emoji: str = ""):
        """
        Display a status message.

        Args:
            message: Status message
            status_type: Type ('success', 'error', 'warning', 'info')
            emoji: Optional emoji prefix
        """
        color_map = {
            "success": "green",
            "error": "red",
            "warning": "yellow",
            "info": "blue",
        }

        color = color_map.get(status_type, "white")
        prefix = f"{emoji} " if emoji else ""

        self.console.print(f"[{color}]{prefix}{message}[/{color}]")
        self.console.print()

    def display_success(self, message: str):
        """Display success message."""
        self.display_status(message, "success", "✅")

    def display_error(self, message: str):
        """Display error message."""
        self.display_status(message, "error", "❌")

    def display_warning(self, message: str):
        """Display warning message."""
        self.display_status(message, "warning", "⚠️")

    def display_info(self, message: str):
        """Display info message."""
        self.display_status(message, "info", "ℹ️")

    def confirm_action(
        self, question: str, default: bool = True, emoji: str = ""
    ) -> bool:
        """
        Ask user for confirmation.

        Args:
            question: Question to ask
            default: Default value
            emoji: Optional emoji prefix

        Returns:
            User's choice
        """
        prefix = f"{emoji} " if emoji else ""
        return Confirm.ask(f"{prefix}{question}", default=default)

    def select_from_menu(
        self,
        title: str,
        options: list[dict],
        show_create_new: bool = False,
        emoji: str = "",
    ) -> str:
        """
        Display a menu and get user selection.

        Args:
            title: Menu title
            options: List of dicts with 'label' and 'value' keys
            show_create_new: Whether to show "Create New" option
            emoji: Optional emoji prefix for title

        Returns:
            Selected value or 'CREATE_NEW'
        """
        table = Table(title=f"{emoji} {title}" if emoji else title, show_header=True)
        table.add_column("Option", style="cyan", no_wrap=True, width=8)
        table.add_column("Description", style="white")

        choices = []
        for i, option in enumerate(options, 1):
            table.add_row(str(i), option["label"])
            choices.append(str(i))

        if show_create_new:
            table.add_row("new", "🆕 Create a new project")
            choices.append("new")

        self.console.print(table)
        self.console.print()

        choice = Prompt.ask(
            "Enter your selection",
            choices=choices,
            default="1" if not show_create_new else None,
        )

        if choice == "new":
            return "CREATE_NEW"

        return options[int(choice) - 1]["value"]

    def get_multiline_input(
        self, prompt_text: str, placeholder: str = "", validate_json: bool = False
    ) -> str:
        """
        Get multiline input from user.

        Args:
            prompt_text: Prompt to display
            placeholder: Placeholder text
            validate_json: Whether to validate as JSON

        Returns:
            User input
        """
        self.console.print(f"[bold]{prompt_text}[/bold]")
        if placeholder:
            self.console.print(f"[dim]{placeholder}[/dim]")
        self.console.print()

        # In Jupyter/IPython, multiline input works with standard input()
        self.console.print("[yellow]Paste your content below and press Enter:[/yellow]")

        lines = []
        try:
            # For single paste, just read one input
            # In Jupyter, pasted multiline content is captured
            content = input()

            if validate_json:
                import json

                try:
                    json.loads(content)
                except json.JSONDecodeError:
                    self.display_error("Invalid JSON format. Please try again.")
                    return self.get_multiline_input(
                        prompt_text, placeholder, validate_json
                    )

            return content

        except EOFError:
            return "\n".join(lines)

    def get_input(
        self, prompt_text: str, default: str = "", choices: list[str] = None
    ) -> str:
        """
        Get single-line input from user.

        Args:
            prompt_text: Prompt to display
            default: Default value
            choices: Optional list of valid choices

        Returns:
            User input
        """
        return Prompt.ask(prompt_text, default=default or None, choices=choices)

    def show_progress(self, description: str, total: int = 100) -> "ProgressContext":
        """
        Create a progress context manager.

        Args:
            description: Progress description
            total: Total steps

        Returns:
            ProgressContext to use with 'with' statement
        """
        return ProgressContext(self.console, description, total)

    def show_spinner(self, description: str) -> "SpinnerContext":
        """
        Create a spinner context manager.

        Args:
            description: Spinner description

        Returns:
            SpinnerContext to use with 'with' statement
        """
        return SpinnerContext(self.console, description)

    def display_instructions(
        self, title: str, steps: list[str], url: str = None, notes: list[str] = None
    ):
        """
        Display formatted instructions.

        Args:
            title: Instruction title
            steps: List of step descriptions
            url: Optional URL to display as a button
            notes: Optional list of notes to display at the end
        """
        content = []

        if url:
            content.append(f"[link={url}]🔗 Click here to open in browser[/link]\n")

        content.append("[bold]📝 Follow these steps:[/bold]\n")

        for i, step in enumerate(steps, 1):
            content.append(f"{i}. {step}")

        if notes:
            content.append("\n[dim]ℹ️ Notes:[/dim]")
            for note in notes:
                content.append(f"[dim]• {note}[/dim]")

        self.display_panel("\n".join(content), title=title, border_style="blue")

    def display_api_status(self, results: dict[str, str], title: str = "API Status"):
        """
        Display API status table.

        Args:
            results: Dict mapping api_name to status
            title: Table title
        """
        table = Table(title=title, show_header=True)
        table.add_column("API", style="cyan")
        table.add_column("Status", style="white")

        for api_name, status in results.items():
            if status in ["enabled", "already_enabled", "working"]:
                status_text = "[green]✅ Enabled[/green]"
            elif status == "testing":
                status_text = "[yellow]⏳ Testing...[/yellow]"
            else:
                status_text = "[red]❌ Error[/red]"

            table.add_row(f"{api_name.title()} API", status_text)

        self.console.print(table)
        self.console.print()

    def display_info_box(self, message: str, box_type: str = "info", title: str = None):
        """
        Display an info/warning/success box.

        Args:
            message: Box content
            box_type: Type ('info', 'warning', 'success', 'error')
            title: Optional title
        """
        style_map = {
            "info": {"border": "blue", "emoji": "ℹ️"},
            "warning": {"border": "yellow", "emoji": "⚠️"},
            "success": {"border": "green", "emoji": "✅"},
            "error": {"border": "red", "emoji": "❌"},
        }

        style = style_map.get(box_type, style_map["info"])
        display_title = f"{style['emoji']} {title}" if title else style["emoji"]

        self.console.print(
            Panel(
                message,
                title=display_title,
                border_style=style["border"],
                title_align="left",
            )
        )
        self.console.print()

    def display_completion(self, user_name: str, project_id: str, apis: list[str]):
        """
        Display completion screen.

        Args:
            user_name: User's name
            project_id: GCP project ID
            apis: List of enabled APIs
        """
        # Create API status table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("API", style="cyan")
        table.add_column("Status", style="green")

        for api in apis:
            table.add_row(f"{api.title()} API", "✅ Working")

        content = [
            f"[bold green]🎉 All set, {user_name}![/bold green]\n",
            "Your Google Workspace APIs are fully configured and tested!\n",
            f"[bold]Project:[/bold] [cyan]{project_id}[/cyan]\n",
        ]

        self.console.print(Panel("\n".join(content), title="✨ Setup Complete!"))
        self.console.print(table)
        self.console.print()

        self.display_info_box(
            "💾 Your OAuth credentials have been saved.\n"
            "Next time you run this setup, we'll automatically load your saved credentials!",
            box_type="success",
            title="Credentials Saved",
        )


class ProgressContext:
    """Context manager for progress bar."""

    def __init__(self, console: Console, description: str, total: int):
        self.console = console
        self.description = description
        self.total = total
        self.progress = None
        self.task = None

    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        )
        self.progress.start()
        self.task = self.progress.add_task(self.description, total=self.total)
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        if self.progress:
            self.progress.stop()

    def update(self, advance: int = 1):
        """Update progress."""
        if self.progress and self.task is not None:
            self.progress.update(self.task, advance=advance)


class SpinnerContext:
    """Context manager for spinner."""

    def __init__(self, console: Console, description: str):
        self.console = console
        self.description = description
        self.progress = None
        self.task = None

    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
        )
        self.progress.start()
        self.task = self.progress.add_task(self.description, total=None)
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        if self.progress:
            self.progress.stop()

    def update(self, description: str):
        """Update spinner description."""
        if self.progress and self.task is not None:
            self.progress.update(self.task, description=description)
