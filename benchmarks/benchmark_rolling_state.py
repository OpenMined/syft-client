"""Benchmark rolling state optimization for fresh login sync.

This benchmark tests the rolling state feature which accumulates events after
a checkpoint, allowing fresh logins to sync with minimal API calls:
- Without rolling state: 1 checkpoint download + N individual event downloads
- With rolling state: 1 checkpoint download + 1 rolling state download

Test scenario:
- Create 4 accepted events (simulating DO processing 4 file changes from DS)
- Checkpoint is created at event 3
- Rolling state accumulates event 4 (1 event)
- Fresh login should verify event 4 is in rolling state
"""

import os
import time
from pathlib import Path
from syft_client.sync.syftbox_manager import SyftboxManager

REPO_ROOT = Path(__file__).parent.parent
CREDENTIALS_DIR = REPO_ROOT / "credentials"
EMAIL_DO = os.environ["BEACH_EMAIL_DO"]
EMAIL_DS = os.environ["BEACH_EMAIL_DS"]
token_path_do = CREDENTIALS_DIR / os.environ.get(
    "beach_credentials_fname_do", "token_do.json"
)
token_path_ds = CREDENTIALS_DIR / os.environ.get(
    "beach_credentials_fname_ds", "token_ds.json"
)

NUM_EVENTS = 4  # Total events to create
CHECKPOINT_THRESHOLD = 3  # Checkpoint after 3 events
EXPECTED_CHECKPOINTS = 1  # Should be 1


def benchmark_rolling_state():
    """Benchmark rolling state performance on fresh login with real GDrive."""
    os.environ["PRE_SYNC"] = "false"

    print("=" * 60)
    print("ROLLING STATE BENCHMARK (GDrive)")
    print("=" * 60)
    print("Configuration:")
    print(f"  DO Email: {EMAIL_DO}")
    print(f"  DS Email: {EMAIL_DS}")
    print(f"  Total events: {NUM_EVENTS}")
    print(f"  Checkpoint threshold: {CHECKPOINT_THRESHOLD}")
    print(f"  Expected checkpoints: {EXPECTED_CHECKPOINTS}")
    print(
        f"  Expected rolling state events: {NUM_EVENTS - (EXPECTED_CHECKPOINTS * CHECKPOINT_THRESHOLD)}"
    )
    print()

    # Clean start - delete any existing syftboxes
    print("Cleaning up existing syftboxes...")
    ds, do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        add_peers=False,
        use_in_memory_cache=False,
    )
    ds.delete_syftbox()
    do.delete_syftbox()

    # Fresh pair for event submission
    print("Creating fresh DS/DO pair...")
    ds, do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        use_in_memory_cache=False,
    )

    # Submit events from DS and have DO process them
    print(f"\nSubmitting {NUM_EVENTS} file changes from DS...")
    submit_start = time.time()

    for i in range(NUM_EVENTS):
        # DS sends a file change
        ds.send_file_change(
            f"{do.email}/file_{i:03d}.txt",
            f"content for file {i} - benchmark rolling state test",
        )
        print(f"  Submitted file {i + 1}/{NUM_EVENTS}")

    submit_time = time.time() - submit_start
    print(f"File change submission complete: {submit_time:.2f}s")

    # Wait for Google Drive to propagate
    print("\nWaiting for Google Drive propagation...")
    time.sleep(5)

    # DO syncs all events (this creates accepted events and triggers checkpointing)
    print("\nDO syncing all events (with auto-checkpoint)...")
    sync_start = time.time()
    do.sync(auto_checkpoint=True)
    do_sync_time = time.time() - sync_start
    print(f"DO sync complete: {do_sync_time:.2f}s")

    # Verify checkpoint and rolling state were created
    checkpoint = do.connection_router.get_latest_checkpoint()
    rolling_state = do.connection_router.get_rolling_state()

    print(f"\nState after {NUM_EVENTS} events:")
    print(f"  Checkpoint exists: {checkpoint is not None}")
    if checkpoint:
        print(f"  Checkpoint files: {len(checkpoint.files)}")
        print(f"  Checkpoint timestamp: {checkpoint.timestamp}")
    print(f"  Rolling state exists: {rolling_state is not None}")
    if rolling_state:
        print(f"  Rolling state events: {rolling_state.event_count}")
        print(
            f"  Rolling state base checkpoint: {rolling_state.base_checkpoint_timestamp}"
        )

    # Wait for Google Drive to propagate checkpoint and rolling state
    print("\nWaiting for Google Drive propagation of checkpoint/rolling state...")
    time.sleep(5)

    # Create a fresh DO manager to simulate initial sync from a new login
    print("\n" + "-" * 60)
    print("SIMULATING FRESH LOGIN")
    print("-" * 60)

    _, fresh_do = SyftboxManager.pair_with_google_drive_testing_connection(
        do_email=EMAIL_DO,
        ds_email=EMAIL_DS,
        do_token_path=token_path_do,
        ds_token_path=token_path_ds,
        use_in_memory_cache=False,
        clear_caches=True,
    )

    # Verify we're using a different cache directory
    assert (
        fresh_do.proposed_file_change_handler.event_cache.file_connection.base_dir
        != do.proposed_file_change_handler.event_cache.file_connection.base_dir
    )

    # Benchmark fresh login sync
    print("\nStarting fresh login sync...")
    sync_start = time.time()
    fresh_do.sync(auto_checkpoint=False)
    fresh_sync_time = time.time() - sync_start

    # Get cache state
    cache = fresh_do.proposed_file_change_handler.event_cache
    files_in_cache = len(cache.file_hashes)

    # Print results
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Total events submitted:         {NUM_EVENTS}")
    print(f"Checkpoint threshold:           {CHECKPOINT_THRESHOLD}")
    print(f"Checkpoints created:            {EXPECTED_CHECKPOINTS}")
    print(
        f"Rolling state events:           {rolling_state.event_count if rolling_state else 0}"
    )
    print()
    print("Timing:")
    print(f"  File change submission:       {submit_time:.2f}s")
    print(f"  Initial DO sync:              {do_sync_time:.2f}s")
    print(f"  Fresh login sync:             {fresh_sync_time:.2f}s")
    print()
    print(f"Files in cache after sync:      {files_in_cache}")
    print()

    return {
        "total_events": NUM_EVENTS,
        "submit_time": submit_time,
        "do_sync_time": do_sync_time,
        "fresh_sync_time": fresh_sync_time,
        "files_in_cache": files_in_cache,
        "checkpoint_files": len(checkpoint.files) if checkpoint else 0,
        "rolling_state_events": rolling_state.event_count if rolling_state else 0,
    }


if __name__ == "__main__":
    results = benchmark_rolling_state()
    print("\nBenchmark complete!")
    print(f"Results: {results}")
