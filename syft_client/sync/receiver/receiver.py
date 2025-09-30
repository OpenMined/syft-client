"""
Receiver server endpoint implementation using syft-serve
"""

import os
from pathlib import Path


def create_receiver_endpoint(email: str, check_interval: int = 1, 
                           process_immediately: bool = True,
                           auto_accept: bool = True,
                           verbose: bool = True):
    """
    Create the receiver server endpoint with syft client integration
    
    Args:
        email: Email address for the receiver
        check_interval: Seconds between inbox checks (default: 30)
        process_immediately: Process existing messages on start (default: True)
        auto_accept: Auto-accept peer requests (default: True)
        verbose: Whether to show status messages (default: True)
    """
    try:
        import syft_serve as ss
    except ImportError:
        raise ImportError("syft-serve is required for receiver. Install with: pip install syft-serve")
    
    import requests
    
    # Create unique server name based on email
    server_name = f"receiver_{email.replace('@', '_').replace('.', '_')}"
    
    # Check if endpoint already exists
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            if verbose:
                print(f"Receiver endpoint already exists for {email}")
            return server
    
    def receiver_main():
        """Main receiver function that runs in the server"""
        import os
        import sys
        import time
        import json
        from pathlib import Path
        from datetime import datetime
        
        # Add the local syft_client to Python path dynamically
        possible_paths = [
            os.environ.get('SYFT_CLIENT_PATH'),
            os.path.expanduser('~/Desktop/Laboratory/syft-client'),
            os.path.expanduser('~/syft-client'),
            os.path.expanduser('~/projects/syft-client'),
            '/opt/syft-client',
        ]
        
        # Find and add the first valid path
        for path in possible_paths:
            if path and os.path.exists(path) and os.path.exists(os.path.join(path, 'syft_client', '__init__.py')):
                if path not in sys.path:
                    sys.path.insert(0, path)
                break
        
        import syft_client as sc
        
        # Silence output if not verbose
        if not verbose:
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')
        
        print(f"Starting receiver for {email}...", flush=True)
        
        # Try to login
    
        client = sc.login(email, verbose=False, force_relogin=False, skip_server_setup=True)
        print(f"Login successful!", flush=True)
    
        # No need for message processor or inbox monitor - check_inbox handles everything
        
        # Track simple statistics
        stats = {
            "start_time": datetime.now().isoformat(),
            "last_check": None,
            "checks_performed": 0,
            "total_messages": 0,
            "peers_checked": 0,
            "errors": 0,
            "last_error": None
        }
        
        # Store for external access
        current_module = sys.modules[__name__]
        current_module.receiver_stats = stats
        current_module.receiver_running = True
        
        print(f"Receiver started. Checking every {check_interval} seconds.", flush=True)
        
        # Process immediately if requested
        if process_immediately:
            print("Processing any existing messages...", flush=True)
        
        # Main receiver loop
        while current_module.receiver_running:
            try:
                stats["last_check"] = datetime.now().isoformat()
                stats["checks_performed"] += 1
                
                # Get all peers
                peer_emails = []
                try:
                    if hasattr(client, 'peers'):
                        peer_emails = list(client.peers)
                except Exception as e:
                    if verbose:
                        print(f"Warning: Could not get peers: {e}", flush=True)
                
                if not peer_emails and verbose:
                    print("No peers configured", flush=True)
                
                # Check each peer's inbox
                total_messages = 0
                for i, peer_email in enumerate(peer_emails):
                    try:
                        stats["peers_checked"] += 1
                        
                        if verbose:
                            print(f"\nChecking inbox from {peer_email}...", flush=True)
                        
                        # Get the actual peer object via indexing
                        peer = client.peers[i]
                        
                        # Check if peer has check_inbox method
                        if hasattr(peer, 'check_inbox'):
                            # Simply call check_inbox - let it use default behavior
                            messages = peer.check_inbox(verbose=verbose)
                            
                            if messages:
                                # Count messages for stats
                                msg_count = sum(len(msg_list) for msg_list in messages.values())
                                total_messages += msg_count
                                stats["total_messages"] += msg_count
                                
                                if verbose:
                                    print(f"  ✓ Found {msg_count} messages")
                        else:
                            if verbose:
                                print(f"  ⚠️  Peer doesn't support check_inbox")
                        
                    except Exception as e:
                        stats["errors"] += 1
                        stats["last_error"] = str(e)
                        if verbose:
                            print(f"  ❌ Error checking {peer_email}: {e}", flush=True)
                
                # Auto-accept peer requests if enabled
                if auto_accept:
                    try:
                        if hasattr(client, 'peers') and hasattr(client.peers, 'requests'):
                            requests = list(client.peers.requests)
                            if requests:
                                print(f"\nAccepting {len(requests)} peer requests...", flush=True)
                                for req_email in requests:
                                    try:
                                        if hasattr(client, 'add_peer'):
                                            client.add_peer(req_email)
                                            print(f"  ✓ Accepted {req_email}", flush=True)
                                    except Exception as e:
                                        print(f"  ✗ Failed to accept {req_email}: {e}", flush=True)
                    except:
                        pass
                
                if verbose and total_messages > 0:
                    print(f"\n✓ Total messages found this cycle: {total_messages}", flush=True)
                
                # Wait for next check
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\nReceiver interrupted", flush=True)
                break
            except Exception as e:
                stats["errors"] += 1
                stats["last_error"] = str(e)
                if verbose:
                    print(f"Error in receiver loop: {e}", flush=True)
                time.sleep(check_interval)
        
        return {
            "status": "stopped",
            "message": f"Receiver stopped after receiving {stats['total_messages']} messages",
            "stats": stats
        }
    
    # Get current syft_client path and set it as environment variable
    import syft_client
    syft_client_path = os.path.dirname(os.path.dirname(os.path.abspath(syft_client.__file__)))
    os.environ['SYFT_CLIENT_PATH'] = syft_client_path
    
    # Create the server
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
            "syft-serve"
        ],
        endpoints={"/": receiver_main},
        force=True
    )
    
    # Give the server time to initialize
    import time
    max_retries = 10
    retry_delay = 1  # seconds
    
    # if verbose:
    #     print(f"Waiting for receiver to initialize...")
    
    for i in range(max_retries):
        try:
            response = requests.get(f"{server.url}/", timeout=2)
            if response.status_code == 200:
                # if verbose:
                #     print(f"✓ Receiver started successfully at {server.url}")
                break
        except requests.exceptions.RequestException:
            if i < max_retries - 1:
                time.sleep(retry_delay)
            else:
                """continue"""
                # if verbose:
                #     print(f"⚠️  Receiver server created but may still be initializing")
                #     print(f"    Server URL: {server.url}")
                #     print(f"    You can check status with: client.receiver.status()")
    
    return server


def destroy_receiver_endpoint(email: str, verbose: bool = True):
    """Destroy the receiver server endpoint for a specific email"""
    try:
        import syft_serve as ss
    except ImportError:
        raise ImportError("syft-serve is required. Install with: pip install syft-serve")
    
    # Create server name to look for
    server_name = f"receiver_{email.replace('@', '_').replace('.', '_')}"
    
    # Find and terminate the specific server
    existing_servers = list(ss.servers)
    for server in existing_servers:
        if server.name == server_name:
            server.terminate()
            if verbose:
                print(f"✓ Receiver for {email} stopped successfully")
            return True
    
    if verbose:
        print(f"No receiver found for {email}")
    return False