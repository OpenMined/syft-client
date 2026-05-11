"""Path filtering utilities for excluding hidden/generated directories from sync and notifications."""

from pathlib import Path

# Directories that should never be synced or included in notifications.
# Checked against individual path components (not substrings).
EXCLUDE_PATTERNS = frozenset(
    {
        ".venv",
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        ".DS_Store",
    }
)


def is_excluded_path(path: str | Path) -> bool:
    """Return True if any component of *path* matches an exclude pattern."""
    parts = Path(path).parts
    return any(part in EXCLUDE_PATTERNS for part in parts)
