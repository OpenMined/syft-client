"""
File watcher server endpoint implementation using syft-serve
"""

import os
import time
from pathlib import Path


def create_watcher_endpoint(email: str, verbose: bool = True):
    """Create the file watcher server endpoint with syft client integration"""
    try:
        import syft_serve as ss
    except ImportError:
        raise ImportError(
            "syft-serve is required for file watching. Install with: pip install syft-serve"
        )

    import requests

    # Check if we're in a Jupyter environment
    def is_jupyter_environment():
        try:
            # Check for IPython kernel
            from IPython import get_ipython

            return (
                get_ipython() is not None
                and get_ipython().__class__.__name__ == "ZMQInteractiveShell"
            )
        except ImportError:
            return False

    # Add retry logic for Jupyter environments where subprocess can fail intermittently
    max_retries = 3 if is_jupyter_environment() else 1
    last_error = None

    # Create unique server name based on email
    server_name = f"watcher_sender_{email.replace('@', '_at_').replace('.', '_')}"

    def watcher_main():
        """Main watcher function that runs in the server"""
        import atexit
        import os
        import sys
        import time
        from pathlib import Path

        # Add the local syft_client to Python path dynamically
        # Look for syft_client in common locations
        possible_paths = [
            os.environ.get("SYFT_CLIENT_PATH"),
            os.path.expanduser("~/Desktop/Laboratory/syft-client"),
            os.path.expanduser("~/syft-client"),
            os.path.expanduser("~/projects/syft-client"),
            "/opt/syft-client",
        ]

        # Also check parent directories of current file
        current_file = os.path.abspath(__file__)
        for i in range(5):  # Go up to 5 levels
            current_file = os.path.dirname(current_file)
            if os.path.exists(os.path.join(current_file, "syft_client", "__init__.py")):
                possible_paths.insert(0, current_file)
                break

        # Find and add the first valid path
        for path in possible_paths:
            if (
                path
                and os.path.exists(path)
                and os.path.exists(os.path.join(path, "syft_client", "__init__.py"))
            ):
                if path not in sys.path:
                    sys.path.insert(0, path)
                break
        else:
            # If no path found, try importing anyway (might be installed via pip)
            pass

        from watchdog.observers import Observer

        import syft_client as sc

        # Import our local modules
        from syft_client.sync.watcher.event_handler import SyftBoxEventHandler
        from syft_client.sync.watcher.sync_history import SyncHistory

        # Login to syft client with provided email
        print(f"Starting watcher for {email}...", flush=True)

        # Try to login - if no credentials exist, create a minimal client
        # Note: login() internally creates SyftBox directory and Colab symlink if needed
        client = sc.login(
            email, verbose=False, force_relogin=False, skip_server_setup=True
        )
        print(f"Login successful!", flush=True)

        # Get the SyftBox directory to watch
        # Always use client's syftbox directory to ensure consistency
        syftbox_dir = client.get_syftbox_directory()

        # Watch the entire datasites folder instead of just the user's own folder
        watch_path = syftbox_dir / "datasites"
        watch_path.mkdir(parents=True, exist_ok=True)

        # Initialize sync history
        sync_history = SyncHistory(syftbox_dir)

        # Warm up sync history with existing files
        print(f"Warming up sync history...", flush=True)
        sync_history.warm_up_from_directory(verbose=verbose)

        # Create event handler
        handler = SyftBoxEventHandler(client, sync_history, verbose=verbose)

        # Create observer and start watching
        observer = Observer()
        observer.schedule(handler, str(watch_path), recursive=True)
        observer.start()

        # Store observer and handler references for cleanup
        current_module = sys.modules[__name__]
        current_module.observer = observer
        current_module.handler = handler
        # Also store the message queue to prevent garbage collection
        if hasattr(handler, "message_queue") and handler.message_queue:
            current_module.message_queue = handler.message_queue
            print(
                f"✅ Message queue stored in module (thread alive: {handler.message_queue._worker_thread.is_alive() if handler.message_queue._worker_thread else 'None'})",
                flush=True,
            )
        else:
            print(f"⚠️ Handler has no message queue", flush=True)

        # Register cleanup function
        def cleanup_observer():
            current_module = sys.modules[__name__]
            if hasattr(current_module, "handler") and current_module.handler:
                current_module.handler.stop()
            if hasattr(current_module, "observer") and current_module.observer:
                print(f"Stopping file watcher for {email}...", flush=True)
                current_module.observer.stop()
                current_module.observer.join()
                print(f"File watcher stopped.", flush=True)

        atexit.register(cleanup_observer)

        # Also start inbox polling for bidirectional sync
        def poll_inbox():
            last_discovery_time = 0
            discovery_interval = 30  # Hard-coded 30 seconds for peer discovery

            while True:
                try:
                    # Check if it's time for peer discovery
                    current_time = time.time()
                    if current_time - last_discovery_time > discovery_interval:
                        if verbose:
                            print(f"🔍 Running peer discovery...", flush=True)
                        try:
                            # Invalidate peer cache to force re-discovery
                            if hasattr(client, "_peer_manager") and hasattr(
                                client._peer_manager, "_invalidate_peers_cache"
                            ):
                                client._peer_manager._invalidate_peers_cache()
                                if verbose:
                                    print(f"   ✓ Peer cache cleared", flush=True)
                        except Exception as e:
                            if verbose:
                                print(
                                    f"   ⚠️  Error during peer discovery: {e}",
                                    flush=True,
                                )
                        last_discovery_time = current_time

                    # Check inbox for all peers
                    peers = []
                    try:
                        if hasattr(client, "peers"):
                            # The client.peers is a property that returns a list-like object
                            peers = list(client.peers)  # Convert to list
                            if verbose and peers:
                                print(
                                    f"📥 Checking inbox for {len(peers)} peer(s)",
                                    flush=True,
                                )
                    except:
                        pass

                    if peers:
                        for peer in peers:
                            try:
                                if hasattr(peer, "check_inbox"):
                                    # check_inbox now handles recording sync history internally
                                    messages = peer.check_inbox(
                                        download_dir=str(syftbox_dir), verbose=False
                                    )
                            except Exception as e:
                                if verbose:
                                    print(
                                        f"Error checking inbox for peer: {e}",
                                        flush=True,
                                    )

                except Exception as e:
                    if verbose:
                        print(f"Error in inbox polling: {e}", flush=True)

                # Wait before next poll
                poll_interval = int(os.environ.get("SYFT_INBOX_POLL_INTERVAL", "30"))
                time.sleep(poll_interval)

        # Start inbox polling in a separate thread
        import threading

        inbox_thread = threading.Thread(target=poll_inbox, daemon=True)
        inbox_thread.start()

        # Start queue status monitoring
        def monitor_queue():
            while True:
                time.sleep(10)  # Check every 10 seconds
                try:
                    if hasattr(current_module, "handler") and current_module.handler:
                        status = current_module.handler.get_queue_status()
                        print(f"📊 Queue Status: {status}", flush=True)
                except Exception as e:
                    print(f"Error getting queue status: {e}", flush=True)

        status_thread = threading.Thread(target=monitor_queue, daemon=True)
        status_thread.start()

        return {
            "status": "started",
            "message": f"Watcher is now monitoring: {watch_path}",
            "email": email,
            "watch_path": str(watch_path),
            "server_name": server_name,
        }

    # Get the current syft_client path and set it as environment variable
    import syft_client

    syft_client_path = os.path.dirname(
        os.path.dirname(os.path.abspath(syft_client.__file__))
    )
    os.environ["SYFT_CLIENT_PATH"] = syft_client_path

    # Retry server creation with backoff for Jupyter environments
    for attempt in range(max_retries):
        try:
            # Create the server without local path in dependencies
            # The watcher_main function will add it to sys.path
            server = ss.create(
                server_name,
                dependencies=[
                    "watchdog",
                    "google-api-python-client",
                    "google-auth",
                    "google-auth-oauthlib",
                    "google-auth-httplib2",
                    "rich",
                    "dnspython",
                    "cryptography",
                    "syft-serve",
                ],
                endpoints={"/": watcher_main},
            )
            break  # Success, exit retry loop
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                if verbose:
                    print(f"⚠️ Watcher creation attempt {attempt + 1} failed: {e}")
                    print(f"🔄 Retrying in {attempt + 1} seconds...")
                time.sleep(attempt + 1)  # Exponential backoff
            else:
                # Final attempt failed, re-raise the error
                raise last_error

    # Trigger the watcher to start
    response = requests.get(server.url)
    if response.status_code == 200:
        # if verbose:
        #     print(f"✓ Watcher started successfully at {server.url}")
        """continue"""
    else:
        print(f"Error starting watcher: {response}")

    return server


def destroy_watcher_endpoint(email: str, verbose: bool = True):
    """Destroy the watcher server endpoint for a specific email"""
    try:
        import syft_serve as ss
    except ImportError:
        raise ImportError(
            "syft-serve is required. Install with: pip install syft-serve"
        )

    # Create server name to look for
    server_name = f"watcher_sender_{email.replace('@', '_at_').replace('.', '_')}"

    # Find and terminate the specific server
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            server.terminate()
            if verbose:
                print(f"✓ Watcher for {email} stopped successfully")
            return True

    if verbose:
        print(f"No watcher found for {email}")
    return False
