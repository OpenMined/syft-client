"""
Interactive log explorer for browsing file versions
"""
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from ..storage.log_storage import LogStorage
from .formatter import format_size, format_timestamp


class LogExplorer:
    """Interactive explorer for append-only log"""
    
    def __init__(self, log_storage: LogStorage):
        self.log_storage = log_storage
        self.current_file: Optional[str] = None
    
    def run(self):
        """Run interactive explorer"""
        print("\n📚 Append-Only Log Explorer")
        print("=" * 50)
        
        while True:
            try:
                self._show_menu()
                choice = input("\nEnter choice: ").strip()
                
                if choice == '1':
                    self._list_files()
                elif choice == '2':
                    self._show_file_history()
                elif choice == '3':
                    self._restore_version()
                elif choice == '4':
                    self._show_stats()
                elif choice == '5' or choice.lower() == 'q':
                    print("\n👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid choice, please try again.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    def _show_menu(self):
        """Display main menu"""
        print("\n📋 Main Menu:")
        print("1. List all tracked files")
        print("2. Show file history")
        print("3. Restore file version")
        print("4. Show statistics")
        print("5. Quit (or press Ctrl+C)")
    
    def _list_files(self):
        """List all tracked files"""
        files = sorted(self.log_storage._index.keys())
        
        if not files:
            print("\n📭 No files tracked yet.")
            return
        
        print(f"\n📁 Tracked files ({len(files)} total):")
        print("-" * 50)
        
        for i, file_path in enumerate(files, 1):
            versions = self.log_storage._index[file_path]
            print(f"{i:3d}. {file_path} ({len(versions)} versions)")
    
    def _show_file_history(self):
        """Show version history for a file"""
        files = sorted(self.log_storage._index.keys())
        
        if not files:
            print("\n📭 No files tracked yet.")
            return
        
        # Select file
        self._list_files()
        try:
            choice = input("\nEnter file number (or path): ").strip()
            
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(files):
                    file_path = files[idx]
                else:
                    print("❌ Invalid file number.")
                    return
            else:
                file_path = choice
                if file_path not in self.log_storage._index:
                    print(f"❌ File not found: {file_path}")
                    return
            
            # Show history
            versions = self.log_storage.get_file_history(file_path)
            print(f"\n📜 History for: {file_path}")
            print(f"   Versions: {len(versions)}")
            print("-" * 80)
            
            for i, version in enumerate(versions):
                print(f"\n{i+1}. Version ID: {version['version_id']}")
                print(f"   Time: {format_timestamp(version['timestamp'])}")
                print(f"   Event: {version['event_type']}")
                
                if version.get('size') is not None:
                    print(f"   Size: {format_size(version['size'])}")
                
                if version.get('hash'):
                    print(f"   Hash: {version['hash'][:16]}...")
            
            self.current_file = file_path
            
        except (ValueError, IndexError):
            print("❌ Invalid input.")
    
    def _restore_version(self):
        """Restore a file version"""
        if not self.current_file:
            self._show_file_history()
            if not self.current_file:
                return
        
        versions = self.log_storage.get_file_history(self.current_file)
        if not versions:
            print("❌ No versions available.")
            return
        
        try:
            choice = input(f"\nEnter version number to restore (1-{len(versions)}): ").strip()
            idx = int(choice) - 1
            
            if 0 <= idx < len(versions):
                version = versions[idx]
                
                # Ask for restore path
                default_path = self.current_file + f".restored_{version['version_id']}"
                restore_path = input(f"Restore to [{default_path}]: ").strip()
                
                if not restore_path:
                    restore_path = default_path
                
                # Restore
                if self.log_storage.restore_version(self.current_file, version['version_id'], restore_path):
                    print(f"✅ Successfully restored to: {restore_path}")
                else:
                    print("❌ Failed to restore version.")
            else:
                print("❌ Invalid version number.")
                
        except ValueError:
            print("❌ Invalid input.")
    
    def _show_stats(self):
        """Show log statistics"""
        total_size = self.log_storage.get_total_size()
        version_count = self.log_storage.get_version_count()
        file_count = len(self.log_storage._index)
        
        print("\n📊 Log Statistics")
        print("-" * 50)
        print(f"Total files tracked: {file_count}")
        print(f"Total versions: {version_count}")
        print(f"Log size: {format_size(total_size)}")
        print(f"Average versions per file: {version_count / file_count if file_count > 0 else 0:.1f}")