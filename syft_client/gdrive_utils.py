"""Download files and folders from Google Drive."""

import io
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from google.oauth2.credentials import Credentials as GoogleCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from syft_client.sync.connections.drive.gdrive_transport import (
    build_drive_service,
    SCOPES,
    GOOGLE_FOLDER_MIME_TYPE,
)
from syft_client.sync.connections.drive.gdrive_retry import (
    execute_with_retries,
    next_chunk_with_retries,
)
from syft_client.sync.utils.syftbox_utils import check_env
from syft_client.sync.environments.environment import Environment
from syft_client.sync.config.config import settings

# Matches strings that could plausibly be a Drive ID:
# - Only base64url chars (alphanumeric, dash, underscore)
# - At least 10 chars long
# - No dots (rules out filenames with extensions)
_COULD_BE_ID = re.compile(r"^[a-zA-Z0-9_-]{10,}$")


def credentials_to_token(
    credentials_path: str | Path,
    output_path: str | Path | None = None,
) -> Path:
    """Convert a Google OAuth credentials.json to an authorized token file.

    Args:
        credentials_path: Path to the OAuth client credentials JSON file.
        output_path: Where to write the token JSON. Defaults to
            ``token.json`` in the same directory as credentials_path.

    Returns:
        Path to the written token file.
    """
    credentials_path = Path(credentials_path)
    if output_path is None:
        output_path = credentials_path.parent / "token.json"
    else:
        output_path = Path(output_path)

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_path.absolute()), SCOPES
    )
    try:
        creds = flow.run_local_server(port=0)
    except Exception:
        flow.redirect_uri = "http://localhost:1"
        auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

        print("Visit this URL to authorize Google Drive access:\n")
        print(f"  {auth_url}\n")
        print("After authorizing, you'll see a page that won't load.")
        print("Copy the 'code' value from the URL in your browser's address bar.")
        print("(The URL looks like: http://localhost:1/?code=XXXXX&scope=...)\n")

        code = input("Paste the authorization code here: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(creds.to_json())
    return output_path


def download_from_gdrive(
    source: str,
    output_path: str | Path,
    token_path: str | Path | None = None,
) -> Path:
    """Download a file or folder from Google Drive.

    Args:
        source: A Google Drive URL, file/folder ID, or filename to search for.
        output_path: Local path. If a directory (or ends with /), the GDrive
            filename is used. Otherwise treated as the target file path.
        token_path: Path to OAuth token JSON. Falls back to SYFTCLIENT_TOKEN_PATH
            env var, then Colab auth.

    Returns:
        Path to the downloaded file or directory.
    """
    service = _build_service(token_path)
    file_id, name, mime_type = _parse_source(service, source)
    is_dir_hint = str(output_path).endswith("/")
    output_path = Path(output_path)

    if mime_type == GOOGLE_FOLDER_MIME_TYPE:
        return _download_folder(service, file_id, output_path, name)

    return _download_single_file(service, file_id, output_path, name, is_dir_hint)


def _build_service(token_path: str | Path | None = None):
    """Build an authenticated Google Drive service."""
    env = check_env()
    if env == Environment.COLAB:
        return build_drive_service(credentials=None, environment=env)

    resolved = token_path or settings.token_path
    if not resolved:
        raise ValueError(
            "No token path provided. Set SYFTCLIENT_TOKEN_PATH env var "
            "or pass token_path explicitly."
        )
    credentials = GoogleCredentials.from_authorized_user_file(str(resolved), SCOPES)
    return build_drive_service(credentials)


def _parse_source(service, source: str) -> tuple[str, str, str]:
    """Resolve source to (file_id, name, mimeType).

    Detection order:
    1. Google Drive URL → extract ID from URL
    2. Could be a raw ID → try API lookup, fall back to name search on 404
    3. Otherwise → search by name
    """
    if _is_gdrive_url(source):
        file_id = _parse_gdrive_url(source)
        return _get_file_metadata(service, file_id)

    if _COULD_BE_ID.match(source):
        result = _try_get_file_metadata(service, source)
        if result is not None:
            return result
        # Not a valid ID, fall through to name search

    return _search_by_name(service, source)


def _is_gdrive_url(source: str) -> bool:
    """Check if source looks like a Google Drive URL."""
    return "drive.google.com" in source or "docs.google.com" in source


def _get_file_metadata(service, file_id: str) -> tuple[str, str, str]:
    """Fetch file metadata by ID. Returns (id, name, mimeType)."""
    metadata = execute_with_retries(
        service.files().get(fileId=file_id, fields="id,name,mimeType")
    )
    return metadata["id"], metadata["name"], metadata["mimeType"]


def _try_get_file_metadata(service, file_id: str) -> tuple[str, str, str] | None:
    """Try to fetch file metadata by ID. Returns None on 404."""
    try:
        return _get_file_metadata(service, file_id)
    except HttpError as e:
        if e.resp.status == 404:
            return None
        raise


def _parse_gdrive_url(url: str) -> str:
    """Extract file/folder ID from a Google Drive URL."""
    parsed = urlparse(url)
    path = parsed.path

    # /file/d/<id>/... or /folders/<id>
    parts = path.split("/")
    for i, part in enumerate(parts):
        if part == "d" and i + 1 < len(parts):
            return parts[i + 1]
        if part == "folders" and i + 1 < len(parts):
            return parts[i + 1]

    # ?id=<id> query parameter
    query_id = parse_qs(parsed.query).get("id")
    if query_id:
        return query_id[0]

    raise ValueError(f"Could not extract file ID from URL: {url}")


def _search_by_name(service, name: str) -> tuple[str, str, str]:
    """Search for a file or folder by name. Returns (id, name, mimeType)."""
    query = f"name='{name}' and trashed=false"
    results = execute_with_retries(
        service.files().list(q=query, fields="files(id,name,mimeType)", pageSize=1)
    )
    files = results.get("files", [])
    if not files:
        raise FileNotFoundError(
            f"No file or folder named '{name}' found on Google Drive"
        )
    f = files[0]
    return f["id"], f["name"], f["mimeType"]


def _download_single_file(
    service,
    file_id: str,
    output_path: Path,
    name: str,
    is_dir_hint: bool = False,
) -> Path:
    """Download a single file from Google Drive."""
    if output_path.is_dir() or is_dir_hint:
        output_path.mkdir(parents=True, exist_ok=True)
        output_path = output_path / name

    output_path.parent.mkdir(parents=True, exist_ok=True)

    request = service.files().get_media(fileId=file_id)
    file_buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(file_buffer, request, chunksize=10 * 1024 * 1024)

    done = False
    while not done:
        _, done = next_chunk_with_retries(downloader)

    output_path.write_bytes(file_buffer.getvalue())
    return output_path


def _download_folder(
    service, folder_id: str, output_dir: Path, folder_name: str
) -> Path:
    """Download all files in a folder (non-recursive, skips subfolders)."""
    target = (
        output_dir / folder_name if not str(output_dir).endswith("/") else output_dir
    )
    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)

    query = f"'{folder_id}' in parents and trashed=false"
    results = execute_with_retries(
        service.files().list(q=query, fields="files(id,name,mimeType)")
    )

    for f in results.get("files", []):
        if f["mimeType"] == GOOGLE_FOLDER_MIME_TYPE:
            continue
        _download_single_file(service, f["id"], target / f["name"], f["name"])

    return target


def _get_default_syftbox_path(email: str) -> Path:
    """Return the default local SyftBox directory for the current environment."""
    env = check_env()
    if env == Environment.COLAB:
        return Path("/content") / f"SyftBox_{email}"
    else:
        return Path.home() / f"SyftBox_{email}"


def read_local_version(local_syftbox_path: Path) -> "VersionInfo | None":
    """Read the local SYFT_version.json from the SyftBox directory.

    Args:
        local_syftbox_path: Path to the local SyftBox directory.

    Returns:
        VersionInfo if the file exists and is valid, None otherwise.
    """
    from syft_client.sync.version.version_info import VersionInfo
    from syft_client.version import VERSION_FILE_NAME

    version_file = local_syftbox_path / VERSION_FILE_NAME
    if not version_file.exists():
        return None
    try:
        return VersionInfo.from_json(version_file.read_text())
    except Exception:
        return None


def write_local_version(local_syftbox_path: Path) -> None:
    """Write current version info to a local SYFT_version.json in the SyftBox directory.

    Creates the SyftBox directory if it doesn't exist.

    Args:
        local_syftbox_path: Path to the local SyftBox directory.
    """
    from syft_client.sync.version.version_info import VersionInfo
    from syft_client.version import VERSION_FILE_NAME

    local_syftbox_path.mkdir(parents=True, exist_ok=True)
    version_file = local_syftbox_path / VERSION_FILE_NAME
    version_file.write_text(VersionInfo.current().to_json())


def _delete_local_syftbox_dirs(local_syftbox_path: Path, verbose: bool = True) -> None:
    """Delete a local SyftBox directory and its companion cache directories."""
    syftbox_name = local_syftbox_path.name
    syftbox_parent = local_syftbox_path.parent
    dirs_to_delete = [
        local_syftbox_path,
        syftbox_parent / f"{syftbox_name}-events",
        syftbox_parent / f"{syftbox_name}-event-messages",
    ]
    for d in dirs_to_delete:
        if d.exists():
            shutil.rmtree(d)
            if verbose:
                print(f"Deleted local directory: {d}")


def _resolve_email_and_token(
    email: str | None, token_path: str | Path | None
) -> tuple[str, Path | None]:
    """Resolve email and token_path for standalone utilities.

    Auto-detects email on Colab. Resolves token_path from env var if needed.

    Returns:
        (email, token_path) tuple.

    Raises:
        ValueError: If email or token_path cannot be resolved.
    """
    env = check_env()

    if env == Environment.COLAB and email is None:
        from syft_client.sync.utils.syftbox_utils import get_email_colab

        email = get_email_colab()

    if email is None:
        raise ValueError(
            "email is required when running locally. On Colab it can be auto-detected."
        )

    if env != Environment.COLAB and token_path is None:
        resolved = settings.token_path
        if not resolved:
            raise ValueError(
                "token_path is required when running locally. "
                "Set SYFTCLIENT_TOKEN_PATH env var or pass token_path explicitly."
            )
        token_path = resolved

    token_path = Path(token_path) if token_path is not None else None
    return email, token_path


def delete_remote_syftbox(
    token_path: str | Path | None = None,
    email: str | None = None,
    verbose: bool = True,
    exclude_ids: set[str] | None = None,
) -> None:
    """Delete all SyftBox state from Google Drive.

    This is a standalone utility that does not require a full SyftboxManager.
    It creates a temporary GDriveConnection to find and delete all SyftBox
    files/folders from Google Drive.

    Note: This function does NOT broadcast ``is_deleted`` events to peers.

    Args:
        token_path: Path to OAuth token JSON file. Required when running
            locally. On Colab, pass ``None`` to use Colab's built-in auth.
        email: Google account email. Required when running locally. On Colab,
            this is auto-detected if not provided.
        verbose: If True (default), print deletion progress.
        exclude_ids: File/folder IDs to skip (e.g. already-archived folders).
    """
    from syft_client.sync.connections.drive.gdrive_transport import GDriveConnection

    email, token_path = _resolve_email_and_token(email, token_path)
    conn = GDriveConnection.from_token_path(email=email, token_path=token_path)

    # Gather file IDs via folder hierarchy
    folder_file_ids = set(conn.gather_all_file_and_folder_ids())

    # Find orphaned syft files by name pattern
    orphaned_file_ids = set(conn.find_orphaned_message_files())

    all_file_ids = folder_file_ids | orphaned_file_ids
    if exclude_ids:
        all_file_ids -= exclude_ids

    all_file_ids = list(all_file_ids)

    start = time.time()
    conn.delete_multiple_files_by_ids(all_file_ids)
    elapsed = time.time() - start

    if verbose:
        orphan_count = len(orphaned_file_ids - folder_file_ids)
        print(
            f"Deleted {len(all_file_ids)} remote files/folders in {elapsed:.2f}s",
            end="",
        )
        if orphan_count > 0:
            print(f" (including {orphan_count} orphaned)")
        else:
            print()

    conn.reset_caches()


def delete_local_syftbox(
    email: str | None = None,
    local_syftbox_path: str | Path | None = None,
    verbose: bool = True,
) -> None:
    """Delete local SyftBox directories.

    Deletes the SyftBox directory and its companion cache directories
    (``<name>-events``, ``<name>-event-messages``).

    Args:
        email: Google account email. Used to resolve default path if
            ``local_syftbox_path`` is not provided.
        local_syftbox_path: Optional path to the local SyftBox directory.
            If not provided, the default path for the current environment
            is used automatically.
        verbose: If True (default), print deletion progress.
    """
    if local_syftbox_path is not None:
        resolved_path = Path(local_syftbox_path)
    else:
        if email is None:
            env = check_env()
            if env == Environment.COLAB:
                from syft_client.sync.utils.syftbox_utils import get_email_colab

                email = get_email_colab()
            if email is None:
                raise ValueError(
                    "email is required to resolve default local path. "
                    "Provide email or local_syftbox_path explicitly."
                )
        resolved_path = _get_default_syftbox_path(email)

    _delete_local_syftbox_dirs(resolved_path, verbose=verbose)


def delete_syftbox(
    token_path: str | Path | None = None,
    email: str | None = None,
    local_syftbox_path: str | Path | None = None,
    verbose: bool = True,
) -> None:
    """Delete all SyftBox state from Google Drive and local directories.

    Convenience wrapper that calls both :func:`delete_remote_syftbox` and
    :func:`delete_local_syftbox`.

    Note: This function does NOT broadcast ``is_deleted`` events to peers.
    Broadcasting requires the full client (peer manager, event cache, encryption
    keys) which are not available in standalone mode. Peers will not be notified
    that files have been removed; they will discover the deletion on their next
    sync cycle.

    Args:
        token_path: Path to OAuth token JSON file. Required when running
            locally. On Colab, pass ``None`` to use Colab's built-in auth.
        email: Google account email. Required when running locally. On Colab,
            this is auto-detected if not provided.
        local_syftbox_path: Optional path to the local SyftBox directory.
            If not provided, the default path for the current environment
            is used automatically.
        verbose: If True (default), print deletion progress.
    """
    # Resolve once for both operations
    email_resolved, token_path_resolved = _resolve_email_and_token(email, token_path)

    delete_remote_syftbox(
        token_path=token_path_resolved,
        email=email_resolved,
        verbose=verbose,
    )
    delete_local_syftbox(
        email=email_resolved,
        local_syftbox_path=local_syftbox_path,
        verbose=verbose,
    )


