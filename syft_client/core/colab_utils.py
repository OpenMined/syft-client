"""
Colab-specific utilities for syft-client

This module provides utilities for enhancing the Google Colab experience,
particularly around filesystem management and symlink creation.
"""

import os
from pathlib import Path
from typing import Optional


def setup_colab_symlink(syftbox_dir: Path, verbose: bool = True) -> Optional[Path]:
    """
    Create a convenience symlink in /content for Colab users.

    In Google Colab, the /content directory is more accessible in the file browser
    and can persist across sessions (with Colab Pro). This function creates a symlink
    from /content/SyftBox_xxx to the actual SyftBox directory (typically in /root).

    This allows users to access their SyftBox data at both locations:
    - /root/SyftBox_xxx (actual data location)
    - /content/SyftBox_xxx (convenience symlink)

    Args:
        syftbox_dir: The actual SyftBox directory path (should be in /root for Colab)
        verbose: Whether to print status messages. Defaults to True.

    Returns:
        Path to the created symlink if successful, None otherwise

    Edge Cases Handled:
        - Not in Colab environment: silently skips
        - /content directory doesn't exist: logs warning and skips
        - Symlink already exists and correct: verifies and skips
        - Symlink exists but points elsewhere: removes and recreates
        - Broken symlink: removes and recreates
        - Path exists as file/directory: logs error and skips
        - Permission denied: logs warning and continues
        - Unexpected errors: logs warning and continues

    Design Philosophy:
        - Idempotent: safe to call multiple times
        - Non-blocking: never raises exceptions
        - Graceful degradation: continues even if symlink creation fails

    Examples:
        >>> from pathlib import Path
        >>> syftbox = Path("/root/SyftBox_user@example.com")
        >>> symlink = setup_colab_symlink(syftbox)
        📎 Created Colab symlink: /content/SyftBox_user@example.com → /root/SyftBox_user@example.com
        >>> symlink
        PosixPath('/content/SyftBox_user@example.com')

        >>> # Calling again is safe (idempotent)
        >>> setup_colab_symlink(syftbox)
        📎 Colab symlink already exists: /content/SyftBox_user@example.com → /root/SyftBox_user@example.com
    """
    # Only run in Colab environment
    # We use a simple heuristic: check if /content exists and we're not in a standard Linux home setup
    # This is more reliable than trying to import google.colab in subprocess contexts
    if not _is_colab_environment():
        return None

    # Verify /content directory exists
    if not os.path.exists("/content"):
        if verbose:
            print("⚠️  /content directory not found, skipping Colab symlink creation")
        return None

    # Create symlink path with same name as the actual directory
    symlink_path = Path("/content") / syftbox_dir.name

    try:
        # Case 1: Symlink already exists
        if symlink_path.is_symlink():
            # Check if it points to the correct target
            current_target = symlink_path.resolve()
            expected_target = syftbox_dir.resolve()

            if current_target == expected_target:
                # Symlink is correct, nothing to do
                if verbose:
                    print(
                        f"📎 Colab symlink already exists: {symlink_path} → {syftbox_dir}"
                    )
                return symlink_path
            else:
                # Symlink points to wrong location, recreate it
                if verbose:
                    print(
                        f"🔧 Removing incorrect symlink: {symlink_path} (pointed to {current_target})"
                    )
                symlink_path.unlink()
                # Fall through to create new symlink

        # Case 2: Path exists as a regular file or directory (not a symlink)
        elif symlink_path.exists():
            path_type = "directory" if symlink_path.is_dir() else "file"
            if verbose:
                print(
                    f"⚠️  Cannot create symlink at {symlink_path}: path already exists as {path_type}"
                )
            return None

        # Case 3: Path doesn't exist or was just removed - create new symlink
        symlink_path.symlink_to(syftbox_dir)
        if verbose:
            print(f"📎 Created Colab symlink: {symlink_path} → {syftbox_dir}")
        return symlink_path

    except PermissionError as e:
        if verbose:
            print(f"⚠️  Permission denied creating Colab symlink at {symlink_path}: {e}")
        return None

    except OSError as e:
        if verbose:
            print(f"⚠️  OS error creating Colab symlink at {symlink_path}: {e}")
        return None

    except Exception as e:
        # Catch-all for any unexpected errors
        # We never want symlink creation to crash the program
        if verbose:
            print(
                f"⚠️  Unexpected error creating Colab symlink: {type(e).__name__}: {e}"
            )
        return None


def _is_colab_environment() -> bool:
    """
    Detect if we're running in Google Colab environment.

    This uses multiple heuristics to reliably detect Colab, even in subprocess contexts
    where importing google.colab might fail.

    Returns:
        True if running in Colab, False otherwise

    Detection Methods (in order):
        1. Check for COLAB_GPU environment variable (set by Colab)
        2. Check if /content directory exists (Colab-specific)
        3. Try importing google.colab module

    Note:
        We deliberately avoid relying solely on google.colab import because:
        - It may not work in syft-serve subprocess contexts
        - Environment detection should be lightweight
        - Filesystem checks are more reliable across contexts
    """
    # Method 1: Check for Colab-specific environment variable
    if "COLAB_GPU" in os.environ or "COLAB_TPU_ADDR" in os.environ:
        return True

    # Method 2: Check for /content directory existence
    # This is less reliable but works in subprocess contexts
    # We also check that we're not in a standard home directory setup
    if os.path.exists("/content"):
        # Additional check: in Colab, /root is typically the home directory
        # and /content is a separate mount point
        try:
            home_dir = Path.home()
            # In Colab: home is /root, and /content exists separately
            # Not in Colab: home might be /home/username or similar
            if home_dir == Path("/root"):
                return True
        except:
            pass

    # Method 3: Try importing google.colab (may fail in subprocesses)
    try:
        import google.colab

        return True
    except (ImportError, AttributeError):
        # ImportError: module not found (not in Colab)
        # AttributeError: sometimes happens in background processes
        pass

    # If none of the methods detected Colab, assume we're not in Colab
    return False


def cleanup_colab_symlink(syftbox_dir: Path, verbose: bool = True) -> bool:
    """
    Remove the Colab convenience symlink if it exists.

    This is typically not needed as symlinks are harmless to leave in place,
    but provided for completeness.

    Args:
        syftbox_dir: The actual SyftBox directory
        verbose: Whether to print status messages

    Returns:
        True if symlink was removed, False otherwise
    """
    if not _is_colab_environment():
        return False

    symlink_path = Path("/content") / syftbox_dir.name

    try:
        if symlink_path.is_symlink():
            symlink_path.unlink()
            if verbose:
                print(f"🗑️  Removed Colab symlink: {symlink_path}")
            return True
        return False
    except Exception as e:
        if verbose:
            print(f"⚠️  Could not remove Colab symlink: {e}")
        return False


__all__ = ["setup_colab_symlink", "cleanup_colab_symlink"]
