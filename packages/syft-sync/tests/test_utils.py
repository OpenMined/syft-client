"""
Test utilities for syft-sync tests
"""
import json
import tarfile
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Union


def extract_syft_archive(archive_path: Path) -> Dict[str, Any]:
    """
    Extract a SyftMessage archive and return information about its contents.
    
    Args:
        archive_path: Path to the .tar.gz archive
        
    Returns:
        Dictionary containing:
        - temp_dir: Path to temporary directory (caller must clean up)
        - message_dir: Path to the message directory within archive
        - data_dir: Path to the data directory
        - metadata_files: List of paths to JSON metadata files
        - data_files: List of paths to files in data directory
    """
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Extract archive
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(temp_dir, filter='data')
        
        extracted_path = Path(temp_dir)
        
        # Find message directory (usually has UUID-like name)
        message_dirs = [d for d in extracted_path.iterdir() if d.is_dir()]
        if not message_dirs:
            raise ValueError("No message directory found in archive")
        
        message_dir = message_dirs[0]
        data_dir = message_dir / "data"
        
        # Find metadata files
        metadata_files = list(message_dir.glob("*.json"))
        
        # Find data files
        data_files = list(data_dir.glob("*")) if data_dir.exists() else []
        
        return {
            "temp_dir": temp_dir,
            "message_dir": message_dir,
            "data_dir": data_dir,
            "metadata_files": metadata_files,
            "data_files": data_files
        }
    except Exception:
        # Clean up on error
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def read_file_from_archive(archive_path: Path, filename: str) -> Union[str, bytes]:
    """
    Read a specific file from a SyftMessage archive.
    
    Args:
        archive_path: Path to the .tar.gz archive
        filename: Name of the file to read from the data directory
        
    Returns:
        File contents as string or bytes
    """
    import shutil
    
    info = extract_syft_archive(archive_path)
    try:
        # Find the file in data directory
        file_path = info["data_dir"] / filename
        if not file_path.exists():
            # Try searching recursively
            found_files = list(info["data_dir"].rglob(filename))
            if not found_files:
                raise FileNotFoundError(f"{filename} not found in archive data directory")
            file_path = found_files[0]
        
        # Try reading as text first, fall back to bytes
        try:
            return file_path.read_text()
        except UnicodeDecodeError:
            return file_path.read_bytes()
    finally:
        # Clean up temp directory
        shutil.rmtree(info["temp_dir"], ignore_errors=True)


def get_archive_metadata(archive_path: Path) -> List[Dict[str, Any]]:
    """
    Extract and return all metadata from a SyftMessage archive.
    
    Args:
        archive_path: Path to the .tar.gz archive
        
    Returns:
        List of metadata dictionaries from all JSON files in the archive
    """
    import shutil
    
    info = extract_syft_archive(archive_path)
    try:
        metadata_list = []
        for metadata_file in info["metadata_files"]:
            with open(metadata_file, 'r') as f:
                metadata_list.append(json.load(f))
        return metadata_list
    finally:
        # Clean up temp directory
        shutil.rmtree(info["temp_dir"], ignore_errors=True)


def verify_syft_message_content(
    archive_path: Path,
    expected_filename: str,
    expected_content: Union[str, bytes],
    expected_sender: str = "syft-watcher@local",
    expected_recipient: str = "log@local"
) -> None:
    """
    Verify the contents of a SyftMessage archive.
    
    Args:
        archive_path: Path to the .tar.gz archive
        expected_filename: Expected filename in data directory
        expected_content: Expected file content
        expected_sender: Expected sender email
        expected_recipient: Expected recipient email
        
    Raises:
        AssertionError if verification fails
    """
    import shutil
    
    info = extract_syft_archive(archive_path)
    try:
        # Verify data directory exists
        assert info["data_dir"].exists(), "Data directory should exist in archive"
        
        # Find and verify file content directly
        file_path = info["data_dir"] / expected_filename
        if not file_path.exists():
            # Try searching recursively
            found_files = list(info["data_dir"].rglob(expected_filename))
            if not found_files:
                raise FileNotFoundError(f"{expected_filename} not found in archive data directory")
            file_path = found_files[0]
        
        # Read content based on expected type
        if isinstance(expected_content, bytes):
            actual_content = file_path.read_bytes()
        else:
            actual_content = file_path.read_text()
        
        assert actual_content == expected_content, f"Content mismatch for {expected_filename}"
        
        # Verify metadata
        assert len(info["metadata_files"]) > 0, "Should have metadata JSON files"
        
        # Check all metadata files for sender/recipient info
        found_sender_info = False
        for metadata in get_archive_metadata(archive_path):
            # Check for sender/recipient (might be at different levels)
            sender = metadata.get('sender') or metadata.get('sender_email')
            recipient = metadata.get('recipient') or metadata.get('recipient_email')
            
            if sender and recipient:
                found_sender_info = True
                assert sender == expected_sender, f"Expected sender {expected_sender}, got {sender}"
                assert recipient == expected_recipient, f"Expected recipient {expected_recipient}, got {recipient}"
        
        assert found_sender_info, "No sender/recipient information found in metadata"
        
    finally:
        # Clean up temp directory
        shutil.rmtree(info["temp_dir"], ignore_errors=True)


def get_version_archive(log_dir: Path, version_id: str) -> Optional[Path]:
    """
    Find the SyftMessage archive for a given version.
    
    Args:
        log_dir: Log directory path
        version_id: Version ID to look for
        
    Returns:
        Path to archive file or None if not found
    """
    # In the new structure, archives are directly in log_dir
    archive_path = log_dir / f"{version_id}.tar.gz"
    return archive_path if archive_path.exists() else None


def verify_version_metadata(log_dir: Path, version_id: str, expected_metadata: Dict[str, Any]) -> None:
    """
    Verify the metadata within a version's archive.
    
    Args:
        log_dir: Log directory path
        version_id: Version ID to check
        expected_metadata: Dictionary of expected metadata key-value pairs
        
    Raises:
        AssertionError if verification fails
    """
    archive_path = get_version_archive(log_dir, version_id)
    assert archive_path is not None, f"Archive for version {version_id} should exist"
    
    # Extract metadata from the archive
    metadata_list = get_archive_metadata(archive_path)
    assert len(metadata_list) > 0, "Should have metadata in archive"
    
    # Find the metadata that contains our event info
    actual_metadata = None
    for metadata in metadata_list:
        if 'version_id' in metadata and metadata['version_id'] == version_id:
            actual_metadata = metadata
            break
    
    assert actual_metadata is not None, f"Could not find metadata for version {version_id} in archive"
    
    for key, expected_value in expected_metadata.items():
        assert key in actual_metadata, f"Metadata should contain key: {key}"
        assert actual_metadata[key] == expected_value, f"Metadata {key} mismatch: expected {expected_value}, got {actual_metadata[key]}"