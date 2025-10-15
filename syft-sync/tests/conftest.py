"""
Pytest configuration and fixtures
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator

from syft_sync import SyftWatcher


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def watch_dir(temp_dir: Path) -> Path:
    """Create a directory to watch"""
    watch_path = temp_dir / "watch"
    watch_path.mkdir()
    return watch_path


@pytest.fixture
def log_dir(temp_dir: Path) -> Path:
    """Create a directory for logs"""
    log_path = temp_dir / "log"
    log_path.mkdir()
    return log_path


@pytest.fixture
def watcher(watch_dir: Path, log_dir: Path) -> SyftWatcher:
    """Create a watcher instance"""
    return SyftWatcher(
        watch_path=str(watch_dir),
        log_path=str(log_dir),
        verbose=False
    )


@pytest.fixture
def sample_file(watch_dir: Path) -> Path:
    """Create a sample file"""
    file_path = watch_dir / "test.txt"
    file_path.write_text("Hello, World!")
    return file_path