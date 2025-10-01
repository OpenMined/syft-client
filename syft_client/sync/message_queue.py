"""
Message queuing and batching for efficient sending
"""

import threading
import time
import queue
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from pathlib import Path
import tempfile
import shutil
import os


@dataclass
class QueuedMessage:
    """A message waiting to be sent"""
    message_type: str  # 'file', 'deletion', 'move'
    source_path: str
    dest_path: Optional[str] = None  # For move messages
    recipient: str = ""  # Empty means send to all peers
    timestamp: float = 0.0
    temp_dir: Optional[str] = None
    prepared_archive: Optional[Tuple[str, str, int]] = None  # (message_id, archive_path, size)


class MessageQueue:
    """
    Handles queuing and batch sending of messages
    """
    
    def __init__(self, sender, batch_interval: float = 0.5, max_batch_size: int = 10):
        """
        Initialize the message queue
        
        Args:
            sender: MessageSender instance
            batch_interval: Time to wait before sending a batch (seconds)
            max_batch_size: Maximum messages to send in one batch
        """
        self.sender = sender
        self.batch_interval = batch_interval
        self.max_batch_size = max_batch_size
        
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = None
        self._is_running = False
        
        # Track prepared messages by recipient
        self._prepared_messages: Dict[str, List[QueuedMessage]] = {}
        self._lock = threading.Lock()
        
    def start(self):
        """Start the queue worker thread"""
        if self._is_running:
            return
            
        self._is_running = True
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        
    def stop(self):
        """Stop the queue worker thread"""
        if not self._is_running:
            return
            
        self._is_running = False
        self._stop_event.set()
        
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
            
        # Clean up any remaining prepared messages
        self._cleanup_prepared_messages()
        
    def queue_file(self, file_path: str):
        """Queue a file to be sent to all peers"""
        message = QueuedMessage(
            message_type='file',
            source_path=file_path,
            timestamp=time.time()
        )
        self._queue.put(message)
        
    def queue_deletion(self, file_path: str):
        """Queue a deletion to be sent to all peers"""
        message = QueuedMessage(
            message_type='deletion',
            source_path=file_path,
            timestamp=time.time()
        )
        self._queue.put(message)
        
    def queue_move(self, source_path: str, dest_path: str):
        """Queue a move to be sent to all peers"""
        message = QueuedMessage(
            message_type='move',
            source_path=source_path,
            dest_path=dest_path,
            timestamp=time.time()
        )
        self._queue.put(message)
        
    def _worker_loop(self):
        """Main worker loop that processes the queue"""
        last_batch_time = time.time()
        
        while self._is_running:
            try:
                # Collect messages for batch interval
                messages_to_process = []
                batch_deadline = last_batch_time + self.batch_interval
                
                while time.time() < batch_deadline and len(messages_to_process) < self.max_batch_size:
                    timeout = max(0.01, batch_deadline - time.time())
                    try:
                        message = self._queue.get(timeout=timeout)
                        messages_to_process.append(message)
                    except queue.Empty:
                        break
                
                # Process collected messages
                if messages_to_process:
                    self._process_batch(messages_to_process)
                    last_batch_time = time.time()
                else:
                    # No messages, just wait a bit
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Error in message queue worker: {e}")
                time.sleep(1.0)  # Back off on error
                
    def _process_batch(self, messages: List[QueuedMessage]):
        """Process a batch of messages"""
        # Get list of peers
        peers_list = list(self.sender.peers.peers)
        if not peers_list:
            if self.sender.client.verbose:
                print("No peers configured")
            return
            
        # Group messages by type and recipient
        messages_by_recipient = {}
        
        for msg in messages:
            # For now, we'll send to all peers
            for peer_email in peers_list:
                if peer_email not in messages_by_recipient:
                    messages_by_recipient[peer_email] = []
                messages_by_recipient[peer_email].append(msg)
        
        # Prepare all messages first
        with self._lock:
            for recipient, recipient_messages in messages_by_recipient.items():
                if recipient not in self._prepared_messages:
                    self._prepared_messages[recipient] = []
                    
                for msg in recipient_messages:
                    try:
                        # Create temp directory for this message
                        temp_dir = tempfile.mkdtemp()
                        msg.temp_dir = temp_dir
                        
                        # Prepare the message based on type
                        if msg.message_type == 'file':
                            prepared = self.sender.prepare_message(
                                msg.source_path, recipient, temp_dir
                            )
                        elif msg.message_type == 'deletion':
                            prepared = self.sender.prepare_deletion_message(
                                msg.source_path, recipient, temp_dir
                            )
                        elif msg.message_type == 'move':
                            prepared = self.sender.prepare_move_message(
                                msg.source_path, msg.dest_path, recipient, temp_dir
                            )
                        else:
                            prepared = None
                            
                        if prepared:
                            msg.prepared_archive = prepared
                            msg.recipient = recipient
                            self._prepared_messages[recipient].append(msg)
                        else:
                            # Clean up temp dir if preparation failed
                            if msg.temp_dir and os.path.exists(msg.temp_dir):
                                shutil.rmtree(msg.temp_dir)
                                
                    except Exception as e:
                        print(f"Error preparing message: {e}")
                        if msg.temp_dir and os.path.exists(msg.temp_dir):
                            shutil.rmtree(msg.temp_dir)
        
        # Now send all prepared messages
        self._send_prepared_batches()
        
    def _send_prepared_batches(self):
        """Send all prepared messages in batches by recipient"""
        with self._lock:
            results_summary = {
                'successful': 0,
                'failed': 0,
                'total': 0
            }
            
            for recipient, messages in self._prepared_messages.items():
                if not messages:
                    continue
                    
                if self.sender.client.verbose:
                    print(f"\n📤 Sending batch of {len(messages)} messages to {recipient}...")
                    
                # Send each message
                for msg in messages:
                    if msg.prepared_archive:
                        message_id, archive_path, archive_size = msg.prepared_archive
                        
                        try:
                            # Send the archive
                            success = self.sender._send_prepared_archive(
                                archive_path, recipient, archive_size, message_id
                            )
                            
                            results_summary['total'] += 1
                            if success:
                                results_summary['successful'] += 1
                                
                                # Record in sync history
                                if msg.message_type == 'deletion':
                                    # For deletions, use path-based hash
                                    import hashlib
                                    path_hash = hashlib.sha256(msg.source_path.encode('utf-8')).hexdigest()
                                    self.sender.client.sync.sync_history.record_sync(
                                        msg.source_path,
                                        message_id,
                                        recipient,
                                        "auto",
                                        "outgoing",
                                        0,
                                        file_hash=path_hash,
                                        operation='delete'
                                    )
                                elif msg.message_type == 'move':
                                    # Record move in sync history
                                    self.sender.client.sync.sync_history.record_move(
                                        msg.source_path,
                                        msg.dest_path,
                                        message_id,
                                        recipient,
                                        "auto",
                                        "outgoing"
                                    )
                                else:
                                    # Regular file sync
                                    self.sender.client.sync.sync_history.record_sync(
                                        msg.source_path,
                                        message_id,
                                        recipient,
                                        "auto",
                                        "outgoing",
                                        archive_size
                                    )
                            else:
                                results_summary['failed'] += 1
                                
                        except Exception as e:
                            print(f"   ❌ Error sending to {recipient}: {e}")
                            results_summary['failed'] += 1
                            results_summary['total'] += 1
                        
                        finally:
                            # Clean up temp directory
                            if msg.temp_dir and os.path.exists(msg.temp_dir):
                                shutil.rmtree(msg.temp_dir)
                
                # Clear processed messages
                messages.clear()
            
            # Print summary
            if self.sender.client.verbose and results_summary['total'] > 0:
                if results_summary['successful'] > 0:
                    print(f"✓ Sent to {results_summary['successful']}/{len(self.sender.peers.peers)} peers")
                else:
                    print(f"Failed to send to any peers")
                    
    def _cleanup_prepared_messages(self):
        """Clean up any remaining prepared messages"""
        with self._lock:
            for recipient, messages in self._prepared_messages.items():
                for msg in messages:
                    if msg.temp_dir and os.path.exists(msg.temp_dir):
                        try:
                            shutil.rmtree(msg.temp_dir)
                        except:
                            pass
            self._prepared_messages.clear()


__all__ = ['MessageQueue', 'QueuedMessage']