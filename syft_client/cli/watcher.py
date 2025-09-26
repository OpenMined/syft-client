"""
syft-watcher: A file watcher CLI tool based on watchdog

This tool monitors a specified folder for file changes and triggers 
configurable actions when changes are detected.
"""

import sys
import time
import logging
import argparse
import json
from pathlib import Path
from typing import Callable, Optional
from datetime import datetime

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
except ImportError:
    print("Error: watchdog library not found. Install it with: pip install watchdog")
    sys.exit(1)

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table


def load_config(config_path: Optional[Path] = None) -> dict:
    """
    Load configuration from JSON file
    
    Args:
        config_path: Path to config file. If None, searches for default locations.
        
    Returns:
        Configuration dictionary
    """
    default_config = {
        "file_patterns": [],
        "ignore_patterns": [".git", "__pycache__", ".DS_Store", "*.pyc", "*.tmp"],
        "recursive": True,
        "action": "default",
        "verbose": False
    }
    
    # Search for config file in default locations
    if config_path is None:
        config_search_paths = [
            Path.cwd() / "syft-watcher.json",
            Path.cwd() / ".syft-watcher.json",
            Path.home() / ".config" / "syft-watcher.json",
            Path.home() / ".syft-watcher.json"
        ]
        
        for path in config_search_paths:
            if path.exists():
                config_path = path
                break
    
    if config_path and config_path.exists():
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
            default_config.update(user_config)
            print(f"[dim]Loaded config from: {config_path}[/dim]")
        except (json.JSONDecodeError, OSError) as e:
            print(f"[yellow]Warning: Could not load config from {config_path}: {e}[/yellow]")
    
    return default_config


def save_sample_config(path: Path) -> None:
    """Save a sample configuration file"""
    sample_config = {
        "file_patterns": ["*.py", "*.js", "*.ts"],
        "ignore_patterns": [".git", "__pycache__", ".DS_Store", "*.pyc", "*.tmp", "node_modules/"],
        "recursive": True,
        "action": "default",
        "verbose": False,
        "_comment": "syft-watcher configuration file. Patterns support shell-style wildcards."
    }
    
    with open(path, 'w') as f:
        json.dump(sample_config, f, indent=2)
    
    print(f"Sample config saved to: {path}")
    print("Edit this file to customize your watcher settings.")


class SyftWatcherHandler(FileSystemEventHandler):
    """File system event handler for syft-watcher"""
    
    def __init__(self, action_func: Callable[[FileSystemEvent], None], 
                 file_patterns: Optional[list] = None,
                 ignore_patterns: Optional[list] = None,
                 console: Optional[Console] = None):
        super().__init__()
        self.action_func = action_func
        self.file_patterns = file_patterns or []
        self.ignore_patterns = ignore_patterns or ['.git', '__pycache__', '.DS_Store', '*.pyc', '*.tmp']
        self.console = console or Console()
        self.event_count = 0
        
    def should_process_event(self, event: FileSystemEvent) -> bool:
        """Determine if an event should be processed based on patterns"""
        file_path = Path(event.src_path)
        
        # Check ignore patterns
        for pattern in self.ignore_patterns:
            if pattern.startswith('*.'):
                # File extension pattern
                if file_path.suffix == pattern[1:]:
                    return False
            elif pattern in str(file_path):
                return False
                
        # Check file patterns (if specified)
        if self.file_patterns:
            for pattern in self.file_patterns:
                if pattern.startswith('*.'):
                    # File extension pattern
                    if file_path.suffix == pattern[1:]:
                        return True
                elif pattern in str(file_path):
                    return True
            return False
            
        return True
    
    def on_any_event(self, event: FileSystemEvent) -> None:
        """Handle any file system event"""
        if event.is_directory:
            return
            
        if not self.should_process_event(event):
            return
            
        self.event_count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Log the event
        self.console.print(f"[dim]{timestamp}[/dim] [bold cyan]{event.event_type}[/bold cyan] {event.src_path}")
        
        # Call the action function
        try:
            self.action_func(event)
        except Exception as e:
            self.console.print(f"[red]Error in action function: {e}[/red]")
            logging.exception("Action function error")


class SyftWatcher:
    """Main watcher class that orchestrates file monitoring"""
    
    def __init__(self, watch_path: str, action_func: Callable[[FileSystemEvent], None],
                 file_patterns: Optional[list] = None,
                 ignore_patterns: Optional[list] = None,
                 recursive: bool = True,
                 verbose: bool = False):
        self.watch_path = Path(watch_path).resolve()
        self.action_func = action_func
        self.file_patterns = file_patterns
        self.ignore_patterns = ignore_patterns
        self.recursive = recursive
        self.verbose = verbose
        
        # Setup console and logging
        self.console = Console()
        self.setup_logging()
        
        # Validate watch path
        if not self.watch_path.exists():
            raise ValueError(f"Watch path does not exist: {self.watch_path}")
        if not self.watch_path.is_dir():
            raise ValueError(f"Watch path is not a directory: {self.watch_path}")
            
        # Create observer and handler
        self.observer = Observer()
        self.handler = SyftWatcherHandler(
            action_func=self.action_func,
            file_patterns=self.file_patterns,
            ignore_patterns=self.ignore_patterns,
            console=self.console
        )
        
    def setup_logging(self) -> None:
        """Setup logging with rich formatting"""
        logging.basicConfig(
            level=logging.DEBUG if self.verbose else logging.INFO,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[RichHandler(console=self.console, rich_tracebacks=True)]
        )
        self.logger = logging.getLogger("syft-watcher")
        
    def start(self) -> None:
        """Start watching for file changes"""
        self.show_startup_info()
        
        # Schedule the observer
        self.observer.schedule(
            self.handler, 
            str(self.watch_path), 
            recursive=self.recursive
        )
        
        # Start the observer
        self.observer.start()
        self.logger.info(f"Started watching: {self.watch_path}")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
            
    def stop(self) -> None:
        """Stop watching and cleanup"""
        self.console.print("\n[yellow]Stopping watcher...[/yellow]")
        self.observer.stop()
        self.observer.join()
        
        # Show summary
        self.console.print(Panel(
            f"[green]Watcher stopped[/green]\n"
            f"Events processed: {self.handler.event_count}",
            title="Summary"
        ))
        
    def show_startup_info(self) -> None:
        """Display startup information"""
        table = Table(title="Syft Watcher Configuration")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Watch Path", str(self.watch_path))
        table.add_row("Recursive", str(self.recursive))
        table.add_row("File Patterns", ", ".join(self.file_patterns) if self.file_patterns else "All files")
        table.add_row("Ignore Patterns", ", ".join(self.ignore_patterns))
        table.add_row("Action Function", self.action_func.__name__)
        
        self.console.print(table)
        self.console.print("\n[dim]Press Ctrl+C to stop watching...[/dim]\n")


def default_action_function(event: FileSystemEvent) -> None:
    """
    Default action function - stub implementation
    
    This function is called whenever a file change is detected.
    Replace this with your custom logic.
    
    Args:
        event: The file system event that triggered this action
               Contains: event_type, src_path, is_directory
    """
    console = Console()
    
    # Example stub actions based on event type
    if event.event_type == "created":
        console.print(f"[green]📁 File created:[/green] {Path(event.src_path).name}")
        # TODO: Add your create action logic here
        pass
        
    elif event.event_type == "modified":
        console.print(f"[yellow]✏️  File modified:[/yellow] {Path(event.src_path).name}")
        # TODO: Add your modify action logic here
        # Example: Re-run tests, rebuild documentation, sync to remote, etc.
        pass
        
    elif event.event_type == "deleted":
        console.print(f"[red]🗑️  File deleted:[/red] {Path(event.src_path).name}")
        # TODO: Add your delete action logic here
        pass
        
    elif event.event_type == "moved":
        console.print(f"[blue]📦 File moved:[/blue] {Path(event.src_path).name}")
        # TODO: Add your move action logic here
        pass
    
    # Example of accessing event details
    if hasattr(event, 'dest_path'):
        console.print(f"[dim]  → to: {event.dest_path}[/dim]")
    
    # Example stub: Print file info
    try:
        file_path = Path(event.src_path)
        if file_path.exists() and file_path.is_file():
            size = file_path.stat().st_size
            console.print(f"[dim]  Size: {size} bytes[/dim]")
    except (OSError, AttributeError):
        pass


def create_custom_action_function() -> Callable[[FileSystemEvent], None]:
    """
    Factory function to create custom action functions
    
    Returns a customized action function with specific behavior.
    Modify this function to implement your specific use case.
    """
    
    def custom_action(event: FileSystemEvent) -> None:
        """Custom action function - implement your logic here"""
        console = Console()
        file_path = Path(event.src_path)
        
        # Example: React to Python file changes
        if file_path.suffix == '.py' and event.event_type == 'modified':
            console.print(f"[magenta]🐍 Python file changed:[/magenta] {file_path.name}")
            
            # Example actions:
            # 1. Run linting
            console.print("[dim]  → Running linting...[/dim]")
            # subprocess.run(['flake8', str(file_path)])
            
            # 2. Run tests
            console.print("[dim]  → Running tests...[/dim]")
            # subprocess.run(['pytest', 'tests/'])
            
            # 3. Generate documentation
            # subprocess.run(['sphinx-build', '-b', 'html', 'docs/', 'docs/_build/'])
            
        # Example: React to configuration file changes
        elif file_path.name in ['pyproject.toml', 'requirements.txt', 'Dockerfile']:
            console.print(f"[red]⚙️  Config file changed:[/red] {file_path.name}")
            console.print("[dim]  → Consider rebuilding environment...[/dim]")
            
        # Example: React to documentation changes
        elif file_path.suffix in ['.md', '.rst']:
            console.print(f"[blue]📝 Documentation changed:[/blue] {file_path.name}")
            console.print("[dim]  → Regenerating docs...[/dim]")
    
    return custom_action


def main() -> None:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="syft-watcher: Monitor files and trigger actions on changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Watch current directory with default action
  syft-watcher .
  
  # Watch specific directory for Python files only
  syft-watcher /path/to/project --patterns "*.py"
  
  # Watch with custom ignore patterns
  syft-watcher . --ignore "*.log" "*.tmp" "build/"
  
  # Non-recursive watching
  syft-watcher . --no-recursive
  
  # Verbose output
  syft-watcher . --verbose
        """
    )
    
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to directory to watch"
    )
    
    parser.add_argument(
        "--patterns", "--include",
        nargs="*",
        help="File patterns to include (e.g., '*.py' '*.js')"
    )
    
    parser.add_argument(
        "--ignore", "--exclude",
        nargs="*",
        default=['.git', '__pycache__', '.DS_Store', '*.pyc', '*.tmp'],
        help="File patterns to ignore (default: .git __pycache__ .DS_Store *.pyc *.tmp)"
    )
    
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Don't watch subdirectories recursively"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--action",
        choices=["default", "custom"],
        default="default",
        help="Action function to use (default: default)"
    )
    
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to configuration file"
    )
    
    parser.add_argument(
        "--save-config",
        type=Path,
        help="Save a sample configuration file and exit"
    )
    
    args = parser.parse_args()
    
    # Handle save-config option
    if args.save_config:
        save_sample_config(args.save_config)
        return
    
    # Check that path is provided when not using save-config
    if not args.path:
        parser.error("the following arguments are required: path (unless using --save-config)")
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command line arguments
    file_patterns = args.patterns or config.get("file_patterns", [])
    ignore_patterns = args.ignore if args.ignore != parser.get_default("ignore") else config.get("ignore_patterns", [])
    recursive = not args.no_recursive if args.no_recursive else config.get("recursive", True)
    verbose = args.verbose or config.get("verbose", False)
    action_type = args.action if args.action != parser.get_default("action") else config.get("action", "default")
    
    # Select action function
    if action_type == "custom":
        action_func = create_custom_action_function()
    else:
        action_func = default_action_function
    
    try:
        # Create and start watcher
        watcher = SyftWatcher(
            watch_path=args.path,
            action_func=action_func,
            file_patterns=file_patterns,
            ignore_patterns=ignore_patterns,
            recursive=recursive,
            verbose=verbose
        )
        
        watcher.start()
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        console = Console()
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()