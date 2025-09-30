"""Base class for all transport layers"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path
from ..environment import Environment


class BaseTransportLayer(ABC):
    """Abstract base class for all transport layers"""
    
    # STATIC Attributes (to be overridden by subclasses)
    # Security
    is_keystore: bool = False  # Do we trust this layer to hold auth keys for other layers?
    
    # Notifications
    is_notification_layer: bool = False  # Does user regularly check this for messages?
    is_html_compatible: bool = False  # Can this layer render HTML?
    is_reply_compatible: bool = False  # Can this layer natively support replies?
    
    # Cross-Platform Interoperability
    guest_submit: bool = False  # Can guests submit without an account?
    guest_read_file: bool = False  # Can guests read files with a URL?
    guest_read_folder: bool = False  # Can guests access folders?
    
    def __init__(self, email: str):
        self.email = email
        # Auto-detect environment on initialization
        from ..environment import detect_environment
        self.environment: Optional[Environment] = detect_environment()
        self.api_is_active: bool = False
        self._cached_credentials: Optional[Dict[str, Any]] = None
        self._platform_client = None  # Will be set by platform client
        
    @property
    def api_is_active_by_default(self) -> bool:
        """Is API active by default in current environment?"""
        # Override in subclasses based on environment
        return False
        
    def set_env_type(self, env: Environment) -> None:
        """Set the environment type"""
        self.environment = env
        
    def get_env_type(self) -> Optional[Environment]:
        """Get the current environment type"""
        return self.environment
    
    def is_cached_as_setup(self) -> bool:
        """Check if this transport is cached as successfully set up"""
        # Cache has been removed, always return False
        return False
        
    @property
    @abstractmethod
    def login_complexity(self) -> int:
        """
        Returns the ADDITIONAL steps required for transport setup.
        
        This is IN ADDITION to platform authentication complexity.
        Total complexity = platform.login_complexity + transport.login_complexity
        
        Returns:
            0: No additional setup needed (just uses platform auth)
            1: One additional step (e.g., enable API)
            2+: Multiple steps (e.g., create project, enable API, create resources)
        """
        pass
    
    @property
    def total_complexity(self) -> int:
        """
        Total login complexity including platform authentication.
        
        Returns:
            -1 if platform auth not available
            Otherwise: platform complexity + transport complexity
        """
        # This would need access to the platform client
        # For now, just return transport complexity
        return self.login_complexity
    
    @staticmethod
    def check_api_enabled(platform_client: Any) -> bool:
        """
        Check if the API for this transport is enabled.
        
        This is a static method that can be called without initializing the transport.
        
        Args:
            platform_client: The platform client with credentials
            
        Returns:
            bool: True if API is enabled, False otherwise
        """
        # Default implementation - subclasses should override
        return False
    
    @staticmethod
    def enable_api_static(transport_name: str, email: str) -> None:
        """
        Static method to show instructions for enabling the API.
        
        Args:
            transport_name: Name of the transport (e.g., 'gmail', 'gdrive_files')
            email: User's email address
        """
        # Default implementation - subclasses should override
        print(f"\n🔧 To enable the API for {transport_name}:")
        print(f"   Please check the platform-specific instructions.")
    
    @staticmethod
    def disable_api_static(transport_name: str, email: str) -> None:
        """
        Static method to show instructions for disabling the API.
        
        Args:
            transport_name: Name of the transport (e.g., 'gmail', 'gdrive_files')
            email: User's email address
        """
        # Default implementation - subclasses should override
        print(f"\n🔧 To disable the API for {transport_name}:")
        print(f"   Please check the platform-specific instructions.")
        
    def setup(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """
        Setup the transport layer with necessary configuration/credentials.
        
        Args:
            credentials: Optional credentials from platform authentication
            
        Returns:
            bool: True if setup successful, False otherwise
        """
        # Default implementation - subclasses can override
        if credentials:
            self._cached_credentials = credentials
        return True
        
    def is_setup(self) -> bool:
        """
        Check if transport layer is properly configured and ready to use.
        
        Returns:
            bool: True if transport is ready, False if setup is needed
        """
        # Default implementation - subclasses should override
        return self._cached_credentials is not None
        
    @abstractmethod
    def send(self, recipient: str, data: Any) -> bool:
        """Send data to a recipient"""
        pass
        
    @abstractmethod
    def receive(self) -> List[Dict[str, Any]]:
        """Receive messages from this transport layer"""
        pass
        
    def contacts(self) -> List[Dict[str, str]]:
        """Get list of contacts and their transport layers"""
        # TODO: Implement contact discovery
        return []
        
    def init(self, verbose: bool = True) -> bool:
        """Initialize transport - for already initialized transports, this is a no-op"""
        if verbose:
            from rich.console import Console
            from rich.panel import Panel
            
            console = Console()
            transport_name = self.__class__.__name__.replace('Transport', '').lower()
            
            # Get platform name if available
            platform_path = "client.platforms.<platform>"
            if hasattr(self, '_platform_client') and self._platform_client:
                platform_name = getattr(self._platform_client, 'platform', '<platform>')
                platform_path = f"client.platforms.{platform_name}"
            
            info_lines = [
                f"[bold green]✓ {transport_name} transport is already initialized![/bold green]",
                "",
                "No action needed - this transport is ready to use.",
                "",
                "[bold]Available methods:[/bold]"
            ]
            
            # Add transport-specific methods
            if 'gmail' in transport_name:
                info_lines.extend([
                    "  • Send emails: [cyan].send(recipient, data, subject)[/cyan]",
                    "  • Read emails: [cyan].receive(limit=10)[/cyan]",
                    "  • Test setup: [cyan].test()[/cyan]"
                ])
            elif 'gdrive' in transport_name.lower():
                info_lines.extend([
                    "  • List files: [cyan].list_files()[/cyan]",
                    "  • Upload file: [cyan].upload_file(filepath)[/cyan]",
                    "  • Download file: [cyan].download_file(file_id, save_path)[/cyan]"
                ])
            elif 'gsheets' in transport_name.lower():
                info_lines.extend([
                    "  • Read sheet: [cyan].read_sheet(spreadsheet_id, range)[/cyan]",
                    "  • Write data: [cyan].write_sheet(spreadsheet_id, range, values)[/cyan]",
                    "  • Create sheet: [cyan].create_sheet(title)[/cyan]"
                ])
            elif 'gforms' in transport_name.lower():
                info_lines.extend([
                    "  • List forms: [cyan].list_forms()[/cyan]",
                    "  • Get responses: [cyan].get_responses(form_id)[/cyan]",
                    "  • Create form: [cyan].create_form(title)[/cyan]"
                ])
            
            info_lines.extend([
                "",
                f"[dim]Access via: {platform_path}.{transport_name}[/dim]"
            ])
            
            panel = Panel("\n".join(info_lines), expand=False, border_style="green")
            console.print(panel)
        
        return True
    
    def __repr__(self):
        """String representation using rich for proper formatting"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from io import StringIO
        
        # Create a string buffer to capture the rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=70)
        
        # Create main table
        main_table = Table(show_header=False, show_edge=False, box=None, padding=0)
        main_table.add_column("Attribute", style="bold cyan")
        main_table.add_column("Value")
        
        # Get the transport name (e.g., 'gmail', 'gdrive_files')
        transport_name = self.__class__.__name__.replace('Transport', '').lower()
        if 'gmail' in transport_name:
            transport_name = 'gmail'
        elif 'gdrive' in transport_name.lower():
            transport_name = 'gdrive_files'
        elif 'gsheets' in transport_name.lower():
            transport_name = 'gsheets'
        elif 'gforms' in transport_name.lower():
            transport_name = 'gforms'
        
        # Transport initialization status
        status = "[green]✓ Initialized[/green]" if self.is_setup() else "[red]✗ Not initialized[/red]"
        main_table.add_row(".is_initialized()", status)
        
        # API status - check if API is enabled using static method
        api_status = "[dim]Unknown[/dim]"
        if hasattr(self, '_platform_client') and self._platform_client:
            # Use the static method to check API status
            try:
                if self.__class__.check_api_enabled(self._platform_client):
                    api_status = "[green]✓ Enabled[/green]"
                else:
                    api_status = "[red]✗ Disabled[/red]"
            except:
                # If check fails, keep as Unknown
                pass
        main_table.add_row(".api_enabled", api_status)
        
        # Environment
        env_name = self.environment.value if self.environment else "Unknown"
        main_table.add_row(".environment", env_name)
        
        # Capabilities
        main_table.add_row("", "")  # spacer
        main_table.add_row("[bold]Capabilities[/bold]", "")
        
        # Add capability rows with actual attribute names
        capabilities = [
            (".is_keystore", self.is_keystore),
            (".is_notification_layer", self.is_notification_layer),
            (".is_html_compatible", self.is_html_compatible),
            (".is_reply_compatible", self.is_reply_compatible),
            (".guest_submit", self.guest_submit),
            (".guest_read_file", self.guest_read_file),
            (".guest_read_folder", self.guest_read_folder),
        ]
        
        for attr_name, value in capabilities:
            icon = "[green]✓[/green]" if value else "[dim]✗[/dim]"
            main_table.add_row(f"  {attr_name}", icon)
        
        # Complexity
        main_table.add_row("", "")  # spacer
        main_table.add_row(".login_complexity", f"{self.login_complexity} steps")
        
        # Key methods
        main_table.add_row("", "")  # spacer
        main_table.add_row("[bold]Methods[/bold]", "")
        main_table.add_row("  .send(recipient, data)", "Send data")
        main_table.add_row("  .receive()", "Get messages") 
        main_table.add_row("  .setup(credentials)", "Configure transport")
        main_table.add_row("  .enable_api()", "Show enable instructions")
        main_table.add_row("  .disable_api()", "Show disable instructions")
        
        # Create the panel showing how to access this transport
        # Try to infer the platform from the email
        platform = "unknown"
        if hasattr(self, '_platform_client'):
            # If we have a reference to the platform client
            platform = getattr(self._platform_client, 'platform', 'unknown')
        elif '@' in self.email:
            # Guess from email domain
            domain = self.email.split('@')[1].lower()
            if 'gmail.com' in domain:
                platform = 'google_personal'
            elif 'google' in domain or 'workspace' in domain:
                platform = 'google_org'
        
        panel_title = f"client.platforms.{platform}.{transport_name}"
        
        panel = Panel(
            main_table,
            title=panel_title,
            expand=False,
            width=70,
            padding=(1, 2)
        )
        
        console.print(panel)
        output = string_buffer.getvalue()
        string_buffer.close()
        
        return output.strip()
    
    def check_api_error(self) -> None:
        """Check and display the last API error for debugging"""
        if hasattr(self, '_last_error'):
            print(f"Last error: {self._last_error}")
        if hasattr(self, '_last_api_error'):
            print(f"API error type: {self._last_api_error}")
        if hasattr(self, '_setup_verified'):
            print(f"Setup verified: {self._setup_verified}")
    
    def enable_api(self) -> None:
        """Guide user through enabling the API for this transport"""
        # Get transport name
        transport_name = self.__class__.__name__.replace('Transport', '').lower()
        if 'gdrive' in transport_name:
            transport_name = 'gdrive_files'
        
        # Get project_id from platform client if available
        project_id = None
        if hasattr(self, '_platform_client') and self._platform_client:
            project_id = getattr(self._platform_client, 'project_id', None)
        
        # Call the static method with project_id
        self.__class__.enable_api_static(transport_name, self.email, project_id)
    
    def disable_api(self) -> None:
        """Show instructions for disabling the API for this transport"""
        # Get transport name
        transport_name = self.__class__.__name__.replace('Transport', '').lower()
        if 'gdrive' in transport_name:
            transport_name = 'gdrive_files'
        
        # Get project_id from platform client if available
        project_id = None
        if hasattr(self, '_platform_client') and self._platform_client:
            project_id = getattr(self._platform_client, 'project_id', None)
        
        # Call the static method with project_id
        self.__class__.disable_api_static(transport_name, self.email, project_id)
    
    def check_inbox(self, sender_email: str, download_dir: Optional[str] = None, verbose: bool = True) -> List[Dict]:
        """
        Base implementation for checking inbox. Transport-specific classes should override
        _get_messages_from_transport() to provide the actual message retrieval logic.
        
        Args:
            sender_email: Email of the sender to check messages from
            download_dir: Directory to download messages to (defaults to SyftBox directory)
            verbose: Whether to print progress
            
        Returns:
            List of message info dicts with keys: id, timestamp, size, metadata, extracted_to
        """
        if not self.is_setup():
            return []
        
        downloaded_messages = []
        
        # Initialize sync history to prevent re-syncing
        sync_history = None
        
        try:
            # Get messages from transport-specific implementation
            messages = self._get_messages_from_transport(sender_email, verbose)
            if not messages:
                return []
            
            # Set up download directory
            if download_dir is None:
                download_dir = self._get_default_download_dir()
            
            download_path = Path(download_dir)
            download_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize sync history for this SyftBox directory
            # Use the root SyftBox directory for sync history, not the download path
            # This ensures consistency with the watcher's sync history
            from ..sync.watcher.sync_history import SyncHistory
            syftbox_root = download_path  # download_path IS the syftbox root
            sync_history = SyncHistory(syftbox_root)
            
            # Process each message
            messages_to_archive = []
            
            for message_info in messages:
                try:
                    # Extract message data
                    message_id = message_info['message_id']
                    message_data = message_info['data']  # Should be raw bytes
                    timestamp = message_info.get('timestamp', '')
                    size_str = message_info.get('size', '0')
                    
                    if verbose:
                        print(f"   📦 Processing message {message_id} ({len(message_data)} bytes)")
                    
                    # Save to temporary file
                    temp_file = download_path / f"{message_id}.tar.gz"
                    with open(temp_file, 'wb') as f:
                        f.write(message_data)
                    
                    # Extract the archive
                    import tarfile
                    extracted_items = []
                    try:
                        with tarfile.open(temp_file, 'r:gz') as tar:
                            # List contents first
                            members = tar.getmembers()
                            if verbose:
                                print(f"   📦 Archive contains {len(members)} items")
                            tar.extractall(download_path)
                            extracted_items = [m.name for m in members]
                    except tarfile.ReadError as e:
                        if verbose:
                            print(f"   ❌ Failed to extract archive: {e}")
                        # Skip this message
                        temp_file.unlink()
                        continue
                        
                    if verbose:
                        # List what was actually extracted
                        print(f"   📂 Extracted to {download_path}:")
                        for item in download_path.iterdir():
                            if item.name.startswith(message_id):
                                print(f"      - {item.name}")
                    
                    # Find the extracted message directory
                    # The directory might have a suffix after the message_id
                    extracted_dir = None
                    for item in download_path.iterdir():
                        if item.is_dir() and item.name.startswith(message_id):
                            extracted_dir = item
                            break
                    
                    if not extracted_dir:
                        # Fallback to exact match
                        extracted_dir = download_path / message_id
                    
                    if verbose:
                        print(f"   📁 Looking for extracted dir: {extracted_dir}")
                        if extracted_dir.exists():
                            print(f"   ✅ Found extracted directory")
                            # List contents
                            for item in extracted_dir.iterdir():
                                print(f"      - {item.name} {'(dir)' if item.is_dir() else '(file)'}")
                        else:
                            print(f"   ❌ Extracted directory not found!")
                    
                    # Read metadata if available
                    metadata = {}
                    metadata_file = extracted_dir / f"{message_id}.json"
                    if metadata_file.exists():
                        import json
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                    
                    # Check if this is a deletion message
                    deletion_manifest_file = extracted_dir / "deletion_manifest.json"
                    if deletion_manifest_file.exists():
                        # Process deletion
                        import json
                        import shutil
                        with open(deletion_manifest_file, 'r') as f:
                            deletion_manifest = json.load(f)
                        
                        if verbose:
                            print(f"   🗑️  Processing deletion message")
                        
                        # Process each deletion
                        for item in deletion_manifest.get('items', []):
                            path_to_delete = download_path / item['path']
                            
                            # FIRST: Record in sync history to prevent echo
                            if sync_history:
                                # Pre-record deletion with hash if file still exists
                                file_hash = None
                                if path_to_delete.exists() and path_to_delete.is_file():
                                    try:
                                        file_hash = sync_history.compute_file_hash(str(path_to_delete))
                                    except:
                                        pass
                                
                                sync_history.record_sync(
                                    str(path_to_delete),
                                    message_id,
                                    sender_email,
                                    self.transport_name,
                                    'incoming',
                                    0,  # Size is 0 for deletions
                                    file_hash=file_hash,
                                    operation='delete'  # Mark this as a deletion
                                )
                                if verbose:
                                    print(f"   📝 Recorded incoming deletion for {path_to_delete}")
                            
                            # THEN: Delete the file/directory
                            if path_to_delete.exists():
                                if path_to_delete.is_dir():
                                    shutil.rmtree(path_to_delete)
                                    if verbose:
                                        print(f"   🗑️  Deleted directory: {path_to_delete.name}")
                                else:
                                    path_to_delete.unlink()
                                    if verbose:
                                        print(f"   🗑️  Deleted file: {path_to_delete.name}")
                            else:
                                if verbose:
                                    print(f"   ℹ️  Already deleted: {path_to_delete.name}")
                        
                        # Add to results
                        downloaded_messages.append({
                            'id': message_id,
                            'timestamp': deletion_manifest.get('timestamp', ''),
                            'size': 0,
                            'metadata': metadata,
                            'operation': 'delete',
                            'deleted_items': deletion_manifest.get('items', [])
                        })
                        
                        # Mark for archiving
                        messages_to_archive.append(message_info)
                    
                    # Process the data files to their final destination
                    elif (data_dir := extracted_dir / "data").exists():
                        if verbose:
                            print(f"   📂 Found data directory, processing files...")
                        # Move files from data dir to their proper location
                        for item in data_dir.iterdir():
                            # Determine destination based on metadata
                            if 'original_path' in metadata:
                                # Use original path from metadata
                                dest = download_path / metadata['original_path'] / item.name
                            else:
                                # Default to root of download dir
                                dest = download_path / item.name
                            
                            # Create parent directories
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            
                            # FIRST: Record sync history BEFORE moving files (to prevent watcher from seeing them)
                            if sync_history:
                                # Helper function to record all files that WILL BE in the destination
                                def record_files_in_source_tree(src_path: Path, dest_path: Path):
                                    if src_path.is_file():
                                        try:
                                            file_size = src_path.stat().st_size
                                            # Compute hash from source file
                                            src_hash = sync_history.compute_file_hash(str(src_path))
                                            if verbose:
                                                print(f"   📝 Pre-recording incoming sync for {dest_path}")
                                            sync_history.record_sync(
                                                str(dest_path),
                                                message_id,
                                                sender_email,
                                                self.transport_name,
                                                'incoming',
                                                file_size,
                                                file_hash=src_hash  # Pass pre-computed hash
                                            )
                                            if verbose:
                                                print(f"   ✅ Pre-recorded incoming sync history")
                                        except Exception as e:
                                            if verbose:
                                                print(f"   ⚠️  Could not pre-record sync history for {dest_path}: {e}")
                                    elif src_path.is_dir():
                                        # Recursively record all files in directory
                                        for child in src_path.iterdir():
                                            child_dest = dest_path / child.name
                                            record_files_in_source_tree(child, child_dest)
                                
                                # Pre-record files BEFORE moving them
                                record_files_in_source_tree(item, dest)
                                
                                # If we have access to file index, mark files as received
                                if hasattr(self._platform_client, '_client') and self._platform_client._client:
                                    client = self._platform_client._client
                                    if hasattr(client, '_file_index') and client._file_index:
                                        # Mark this file as received from sender
                                        client._file_index.mark_as_received(str(dest), sender_email)
                            
                            # THEN: Move the file/directory
                            if item.is_dir():
                                if dest.exists():
                                    # Merge directories instead of replacing
                                    self._merge_directories(str(item), str(dest))
                                else:
                                    import shutil
                                    shutil.move(str(item), str(dest))
                            else:
                                # For files, overwrite if exists
                                if dest.exists():
                                    dest.unlink()
                                import shutil
                                shutil.move(str(item), str(dest))
                            
                            if verbose:
                                print(f"   📥 Extracted: {dest.name}")
                    
                        # Add to results
                        downloaded_messages.append({
                            'id': message_id,
                            'timestamp': timestamp,
                            'size': int(size_str) if str(size_str).isdigit() else 0,
                            'metadata': metadata,
                            'extracted_to': str(download_path)
                        })
                        
                        # Mark for archiving
                        messages_to_archive.append(message_info)
                    
                    # Clean up temporary files
                    temp_file.unlink()
                    if extracted_dir.exists():
                        import shutil
                        shutil.rmtree(extracted_dir)
                    
                except Exception as e:
                    if verbose:
                        print(f"   ❌ Error processing message {message_info.get('message_id', 'unknown')}: {e}")
                        import traceback
                        traceback.print_exc()
            
            # Archive processed messages
            if messages_to_archive:
                self._archive_messages(messages_to_archive, verbose)
            
            return downloaded_messages
            
        except Exception as e:
            if verbose:
                print(f"   ❌ Error checking inbox: {e}")
            return []
    
    def _get_messages_from_transport(self, sender_email: str, verbose: bool = True) -> List[Dict]:
        """
        Transport-specific method to retrieve messages. Must be overridden by subclasses.
        
        Should return a list of dicts with:
        - message_id: Unique identifier for the message
        - data: Raw bytes of the message (tar.gz archive)
        - timestamp: When the message was sent
        - size: Size of the message in bytes
        - any other transport-specific info needed for archiving
        """
        return []
    
    def _archive_messages(self, messages: List[Dict], verbose: bool = True):
        """
        Transport-specific method to archive processed messages. Override in subclasses.
        """
        pass
    
    def _get_default_download_dir(self) -> str:
        """
        Get the default download directory (SyftBox directory)
        """
        if hasattr(self._platform_client, '_client') and self._platform_client._client:
            client = self._platform_client._client
            if hasattr(client, 'local_syftbox_dir') and client.local_syftbox_dir:
                return str(client.local_syftbox_dir)
        
        # Fallback to home directory pattern
        return str(Path.home() / f"SyftBox_{self.email}")
    
    @property
    def transport_name(self) -> str:
        """
        Get the name of this transport (e.g., 'gdrive_files', 'gsheets')
        """
        # Default implementation based on class name
        name = self.__class__.__name__.replace('Transport', '').lower()
        if 'gdrive' in name:
            return 'gdrive_files'
        elif 'gsheets' in name:
            return 'gsheets'
        elif 'gmail' in name:
            return 'gmail'
        elif 'gforms' in name:
            return 'gforms'
        return name
    
    def _merge_directories(self, src: str, dest: str) -> None:
        """
        Recursively merge src directory into dest directory.
        Only files are moved, directories are created as needed.
        Files in src will overwrite files in dest with the same name.
        """
        import shutil
        from pathlib import Path
        
        src_path = Path(src)
        dest_path = Path(dest)
        
        # Ensure destination directory exists
        dest_path.mkdir(parents=True, exist_ok=True)
        
        for item in src_path.iterdir():
            s = item
            d = dest_path / item.name
            
            if s.is_dir():
                # Always recurse into directories, never move them wholesale
                self._merge_directories(str(s), str(d))
            else:
                # For files, move (overwriting if exists)
                if d.exists():
                    d.unlink()
                shutil.move(str(s), str(d))
    
    def send_to(self, archive_path: str, recipient: str, message_id: Optional[str] = None) -> bool:
        """
        Base implementation for sending messages. Transport-specific classes should override
        _send_archive_via_transport() to provide the actual sending logic.
        
        Args:
            archive_path: Path to the prepared .syftmsg archive
            recipient: Email address of the recipient
            message_id: Optional message ID for tracking
            
        Returns:
            True if send was successful, False otherwise
        """
        if not self.is_setup():
            return False
            
        try:
            # Validate archive exists
            import os
            if not os.path.exists(archive_path):
                if hasattr(self, 'verbose') and self.verbose:
                    print(f"❌ Archive not found: {archive_path}")
                return False
            
            # Read archive file
            with open(archive_path, 'rb') as f:
                archive_data = f.read()
            
            # Get filename
            filename = os.path.basename(archive_path)
            if message_id and not filename.startswith(message_id):
                filename = f"{message_id}_{filename}"
            
            # Call transport-specific implementation
            return self._send_archive_via_transport(
                archive_data=archive_data,
                filename=filename,
                recipient=recipient,
                message_id=message_id
            )
            
        except Exception as e:
            if hasattr(self, 'verbose') and self.verbose:
                print(f"❌ Error sending via {self.transport_name}: {e}")
            return False
    
    def _send_archive_via_transport(self, archive_data: bytes, filename: str, 
                                   recipient: str, message_id: Optional[str] = None) -> bool:
        """
        Transport-specific method to send the archive data. Must be overridden by subclasses.
        
        Args:
            archive_data: Raw bytes of the archive file
            filename: Suggested filename for the archive
            recipient: Email address of the recipient
            message_id: Optional message ID for tracking
            
        Returns:
            True if send was successful, False otherwise
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement _send_archive_via_transport()")