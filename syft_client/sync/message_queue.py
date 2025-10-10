"""
Message queuing and batching for efficient sending
"""

import os
import queue
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class QueuedMessage:
    """A message waiting to be sent"""

    message_type: str  # 'file', 'deletion', 'move'
    source_path: str
    dest_path: Optional[str] = None  # For move messages
    recipient: str = ""  # Empty means send to all peers
    timestamp: float = 0.0
    temp_dir: Optional[str] = None
    prepared_archive: Optional[Tuple[str, str, int]] = (
        None  # (message_id, archive_path, size)
    )


class MessageQueue:
    """
    Handles queuing and batch sending of messages
    """

    def __init__(self, sender, batch_interval: float = 2.0, max_batch_size: int = 10):
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
            print("📋 Message queue already running", flush=True)
            return

        print(f"📋 Starting message queue worker thread...", flush=True)
        self._is_running = True
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        print(f"📋 Worker thread started: {self._worker_thread.is_alive()}", flush=True)

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

    def flush_queue(self):
        """Manually flush all queued messages immediately"""
        print(f"🚀 Manually flushing message queue...", flush=True)

        # Collect all messages currently in queue
        messages_to_process = []
        while not self._queue.empty():
            try:
                message = self._queue.get_nowait()
                messages_to_process.append(message)
            except queue.Empty:
                break

        if messages_to_process:
            print(
                f"📦 Force processing batch of {len(messages_to_process)} messages",
                flush=True,
            )
            self._process_batch(messages_to_process)
        else:
            print(f"📭 No messages in queue to flush", flush=True)

    def queue_file(self, file_path: str):
        """Queue a file to be sent to all peers"""
        message = QueuedMessage(
            message_type="file", source_path=file_path, timestamp=time.time()
        )
        self._queue.put(message)
        if self.sender.client.verbose:
            print(
                f"📋 Queued file message: {file_path} (queue size: {self._queue.qsize()})",
                flush=True,
            )
            print(
                f"   ⏰ Will be sent in next batch (within {self.batch_interval}s)",
                flush=True,
            )
            # Check if worker is alive
            if self._worker_thread and self._worker_thread.is_alive():
                print(f"   ✅ Worker thread is running", flush=True)
            else:
                print(f"   ❌ Worker thread is NOT running!", flush=True)
                # Try to restart it
                print(f"   🔄 Attempting to restart worker thread...", flush=True)
                self.start()

            # Disabled force flush to avoid overwhelming the API
            # if self._queue.qsize() >= 3:
            #     print(f"   🚀 Queue has {self._queue.qsize()} messages, forcing immediate processing", flush=True)
            #     self.flush_queue()

    def queue_deletion(self, file_path: str):
        """Queue a deletion to be sent to all peers"""
        message = QueuedMessage(
            message_type="deletion", source_path=file_path, timestamp=time.time()
        )
        self._queue.put(message)

    def queue_move(self, source_path: str, dest_path: str):
        """Queue a move to be sent to all peers"""
        message = QueuedMessage(
            message_type="move",
            source_path=source_path,
            dest_path=dest_path,
            timestamp=time.time(),
        )
        self._queue.put(message)
        if self.sender.client.verbose:
            print(
                f"📋 Queued move message: {source_path} → {dest_path} (queue size: {self._queue.qsize()})",
                flush=True,
            )

    def _worker_loop(self):
        """Main worker loop that processes the queue"""
        print(f"📋 Entering worker loop method", flush=True)

        # Write to debug log file
        try:
            import os

            debug_file = os.path.expanduser("~/syft_message_queue_debug.log")
            with open(debug_file, "a") as f:
                f.write(
                    f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Worker loop started\n"
                )
                f.flush()
        except:
            pass

        try:
            verbose = getattr(self.sender.client, "verbose", True)
        except Exception as e:
            print(f"❌ Error getting verbose flag: {e}", flush=True)
            verbose = True

        last_batch_time = time.time()

        if verbose:
            print(f"📋 Message queue worker started", flush=True)
            print(f"   Batch interval: {self.batch_interval}s", flush=True)
            print(f"   Max batch size: {self.max_batch_size}", flush=True)

        # Add heartbeat counter
        heartbeat_count = 0
        last_heartbeat = time.time()
        messages_processed_total = 0

        print(f"🚀 Worker loop starting main loop, verbose={verbose}", flush=True)

        while self._is_running:
            try:
                # Print heartbeat every 5 seconds (always, not just verbose)
                if time.time() - last_heartbeat > 5.0:
                    heartbeat_count += 1
                    queue_size = self._queue.qsize()
                    print(
                        f"💓 Worker heartbeat #{heartbeat_count} (queue: {queue_size}, processed: {messages_processed_total})",
                        flush=True,
                    )
                    last_heartbeat = time.time()

                    # Also log to file
                    try:
                        debug_file = os.path.expanduser(
                            "~/syft_message_queue_debug.log"
                        )
                        with open(debug_file, "a") as f:
                            f.write(
                                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Heartbeat #{heartbeat_count} - Queue: {queue_size}, Processed: {messages_processed_total}\n"
                            )
                            f.flush()
                    except:
                        pass

                    # If we have messages but haven't processed any, force flush
                    if queue_size > 0 and messages_processed_total == 0:
                        print(
                            f"⚠️  Queue has messages but none processed, forcing flush",
                            flush=True,
                        )
                        self.flush_queue()
                        continue

                # Collect messages for batch interval
                messages_to_process = []
                batch_deadline = last_batch_time + self.batch_interval

                # Debug: show we're in the loop
                current_queue_size = self._queue.qsize()
                if current_queue_size > 0 and verbose:
                    print(
                        f"📋 Worker checking queue (size: {current_queue_size}, deadline in: {batch_deadline - time.time():.2f}s)",
                        flush=True,
                    )

                while (
                    time.time() < batch_deadline
                    and len(messages_to_process) < self.max_batch_size
                ):
                    timeout = max(0.01, batch_deadline - time.time())
                    try:
                        message = self._queue.get(timeout=timeout)
                        messages_to_process.append(message)
                        if verbose:
                            print(
                                f"   📥 Collected message: {message.message_type} for {message.source_path}",
                                flush=True,
                            )
                    except queue.Empty:
                        # Check if we should exit the collection loop
                        if (
                            time.time() >= batch_deadline
                            or len(messages_to_process) >= self.max_batch_size
                        ):
                            break
                        # Otherwise continue waiting
                        continue

                # Process collected messages
                if messages_to_process:
                    if verbose:
                        print(
                            f"\n📦 Processing batch of {len(messages_to_process)} messages",
                            flush=True,
                        )
                    self._process_batch(messages_to_process)
                    messages_processed_total += len(messages_to_process)
                else:
                    # No messages, just wait a bit
                    time.sleep(0.1)

                # Always update last_batch_time after processing or timeout
                last_batch_time = time.time()

            except Exception as e:
                print(f"❌ Error in message queue worker: {e}", flush=True)
                import traceback

                traceback.print_exc()
                time.sleep(1.0)  # Back off on error

    def _process_batch(self, messages: List[QueuedMessage]):
        """Process a batch of messages"""
        # Get list of peers
        try:
            if self.sender.client.verbose:
                print(f"📋 Getting peers list...", flush=True)
                print(f"   sender type: {type(self.sender)}", flush=True)
                print(f"   sender.peers type: {type(self.sender.peers)}", flush=True)

            peers_list = list(self.sender.peers.peers)

            if self.sender.client.verbose:
                print(f"   Found {len(peers_list)} peers: {peers_list}", flush=True)

        except Exception as e:
            print(f"❌ Error getting peers list: {e}", flush=True)
            print(f"   sender attributes: {dir(self.sender)}", flush=True)
            return

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
                # Create a copy of the message for each recipient
                # This ensures each recipient gets their own temp directory and archive
                msg_copy = QueuedMessage(
                    source_path=msg.source_path,
                    message_type=msg.message_type,
                    dest_path=msg.dest_path,
                )
                messages_by_recipient[peer_email].append(msg_copy)

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

                        # Debug: Log temp directory creation
                        if self.sender.client.verbose:
                            print(
                                f"   📁 Created temp dir for {recipient}: {temp_dir}",
                                flush=True,
                            )

                        # Prepare the message based on type
                        if msg.message_type == "file":
                            prepared = self.sender.prepare_message(
                                msg.source_path, recipient, temp_dir
                            )
                        elif msg.message_type == "deletion":
                            prepared = self.sender.prepare_deletion_message(
                                msg.source_path, recipient, temp_dir
                            )
                        elif msg.message_type == "move":
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
        # Get verbose flag once
        try:
            verbose = getattr(self.sender.client, "verbose", True)
        except:
            verbose = True

        with self._lock:
            results_summary = {"successful": 0, "failed": 0, "total": 0}

            for recipient, messages in self._prepared_messages.items():
                if not messages:
                    continue

                if verbose:
                    print(
                        f"\n📤 Sending batch of {len(messages)} messages to {recipient}..."
                    )

                # Send each message
                for msg in messages:
                    if msg.prepared_archive:
                        message_id, archive_path, archive_size = msg.prepared_archive

                        try:
                            # Send the archive with retry logic
                            if verbose:
                                print(
                                    f"   📨 Sending {message_id} to {recipient} (size: {archive_size})",
                                    flush=True,
                                )

                            # Try up to 3 times with exponential backoff
                            success = False
                            max_retries = 3
                            for attempt in range(max_retries):
                                if attempt > 0:
                                    # Wait before retry (1s, 2s, 4s)
                                    wait_time = 2 ** (attempt - 1)
                                    if verbose:
                                        print(
                                            f"   ⏳ Retry attempt {attempt + 1}/{max_retries} after {wait_time}s wait...",
                                            flush=True,
                                        )
                                    time.sleep(wait_time)

                                success = self.sender._send_prepared_archive(
                                    archive_path, recipient, archive_size, message_id
                                )

                                if success:
                                    break
                                elif verbose and attempt < max_retries - 1:
                                    print(
                                        f"   ⚠️  Send failed, will retry...", flush=True
                                    )

                            if verbose:
                                print(
                                    f"   {'✅' if success else '❌'} Final result: {success}",
                                    flush=True,
                                )

                            results_summary["total"] += 1
                            if success:
                                results_summary["successful"] += 1

                                # Record in sync history
                                if msg.message_type == "deletion":
                                    # For deletions, use path-based hash
                                    import hashlib

                                    path_hash = hashlib.sha256(
                                        msg.source_path.encode("utf-8")
                                    ).hexdigest()
                                    # Access sync_history through the watcher's sync_history, not client.sync
                                    if hasattr(self.sender.client, "sync_history"):
                                        self.sender.client.sync_history.record_sync(
                                            msg.source_path,
                                            message_id,
                                            recipient,
                                            "auto",
                                            "outgoing",
                                            0,
                                            file_hash=path_hash,
                                            operation="delete",
                                        )
                                elif msg.message_type == "move":
                                    # Record move in sync history
                                    if hasattr(self.sender.client, "sync_history"):
                                        # Assuming record_move exists on sync_history
                                        # If not, we'll skip recording
                                        if hasattr(
                                            self.sender.client.sync_history,
                                            "record_move",
                                        ):
                                            self.sender.client.sync_history.record_move(
                                                msg.source_path,
                                                msg.dest_path,
                                                message_id,
                                                recipient,
                                                "auto",
                                                "outgoing",
                                            )
                                else:
                                    # Regular file sync
                                    if hasattr(self.sender.client, "sync_history"):
                                        self.sender.client.sync_history.record_sync(
                                            msg.source_path,
                                            message_id,
                                            recipient,
                                            "auto",
                                            "outgoing",
                                            archive_size,
                                        )
                            else:
                                results_summary["failed"] += 1

                        except Exception as e:
                            print(f"   ❌ Error sending to {recipient}: {e}")
                            results_summary["failed"] += 1
                            results_summary["total"] += 1

                        finally:
                            # Clean up temp directory
                            if msg.temp_dir and os.path.exists(msg.temp_dir):
                                shutil.rmtree(msg.temp_dir)

                # Clear processed messages
                messages.clear()

            # Print summary
            if verbose and results_summary["total"] > 0:
                if results_summary["successful"] > 0:
                    try:
                        num_peers = len(self.sender.peers.peers)
                    except:
                        num_peers = "?"
                    unique_recipients = len(self._prepared_messages)
                    print(
                        f"✓ Sent {results_summary['successful']} messages to {unique_recipients} peers (total peers: {num_peers})"
                    )
                    print(
                        f"   Total attempts: {results_summary['total']}, Failed: {results_summary['failed']}"
                    )
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


__all__ = ["MessageQueue", "QueuedMessage"]
