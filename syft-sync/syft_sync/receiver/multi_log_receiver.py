"""
Multi-Log Receiver - Watches multiple log directories and syncs to one output
"""
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
import threading

from .log_receiver import LogReceiver
from .syft_log_receiver import SyftLogReceiver


logger = logging.getLogger(__name__)


class SyftReceiver:
    """
    Receiver that watches multiple log directories and syncs to a single output directory.
    Designed for P2P scenarios where a party receives from multiple sources.
    """
    
    def __init__(
        self,
        log_paths: List[str],
        output_path: str,
        exclude_patterns: Optional[List[str]] = None,
        verbose: bool = False,
        sync_mode: str = "latest",
        lock_file_suffix: str = ".sync_lock",
        lock_file_delay: float = 1.0,
        use_syft: bool = True
    ):
        """
        Initialize multi-log receiver
        
        Args:
            log_paths: List of log directories to watch
            output_path: Directory where files will be synced
            exclude_patterns: Patterns to exclude from syncing
            verbose: Print detailed output
            sync_mode: "latest" or "all_versions"
            lock_file_suffix: Suffix for lock files
            lock_file_delay: Delay before removing lock files
            use_syft: Use SyftLogReceiver (True) or regular LogReceiver
        """
        self.log_paths = [Path(p) for p in log_paths]
        self.output_path = Path(output_path)
        self.verbose = verbose
        
        # Create a receiver for each log path
        self.receivers = []
        ReceiverClass = SyftLogReceiver if use_syft else LogReceiver
        
        for log_path in self.log_paths:
            receiver = ReceiverClass(
                log_path=str(log_path),
                output_path=str(output_path),
                exclude_patterns=exclude_patterns,
                verbose=False,  # Individual receivers less verbose
                sync_mode=sync_mode,
                lock_file_suffix=lock_file_suffix,
                lock_file_delay=lock_file_delay
            )
            self.receivers.append(receiver)
        
        if verbose:
            logger.info(f"📥 Multi-Log Receiver initialized")
            logger.info(f"   Watching {len(self.log_paths)} log paths:")
            for lp in self.log_paths:
                logger.info(f"     - {lp}")
            logger.info(f"   Output path: {self.output_path}")
            logger.info(f"   Sync mode: {sync_mode}")
    
    def start(self):
        """Start all receivers"""
        if self.verbose:
            logger.info(f"🚀 Starting {len(self.receivers)} receivers...")
        
        for i, receiver in enumerate(self.receivers):
            receiver.start()
            if self.verbose:
                logger.info(f"   ✓ Receiver {i+1} started: {self.log_paths[i]}")
    
    def stop(self):
        """Stop all receivers"""
        if self.verbose:
            logger.info(f"🛑 Stopping {len(self.receivers)} receivers...")
        
        for receiver in self.receivers:
            receiver.stop()
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get combined sync status from all receivers"""
        total_files = 0
        total_versions = 0
        
        for receiver in self.receivers:
            status = receiver.get_sync_status()
            total_files += status.get('files_tracked', 0)
            total_versions += status.get('versions_processed', 0)
        
        return {
            'receivers': len(self.receivers),
            'log_paths': [str(p) for p in self.log_paths],
            'output_path': str(self.output_path),
            'total_files_tracked': total_files,
            'total_versions_processed': total_versions
        }
    
    def get_receiver_stats(self) -> List[Dict[str, Any]]:
        """Get individual stats for each receiver"""
        stats = []
        for i, receiver in enumerate(self.receivers):
            receiver_stats = receiver.get_sync_status()
            receiver_stats['log_path'] = str(self.log_paths[i])
            stats.append(receiver_stats)
        return stats
