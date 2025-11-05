from pathlib import Path
import os
from typing import Optional, Union


def resolve_path(
    path: Union[str, Path], syftbox_folder: Optional[Union[str, Path]] = None
) -> Path:
    """
    Resolve syft:// paths to absolute filesystem paths.

    This function converts syft:// URLs to actual filesystem paths by replacing
    the syft:// prefix with the SyftBox folder location.

    Args:
        path: Path to resolve (e.g., "syft://path/to/dir")
        syftbox_folder: SyftBox folder location. If not provided, will use
                       SYFTBOX_FOLDER environment variable.

    Returns:
        Resolved pathlib.Path object

    Raises:
        ValueError: If syftbox_folder not provided and SYFTBOX_FOLDER env var not set
        ValueError: If path doesn't start with syft://

    Examples:
        >>> resolve_path("syft://datasites/user/data", "/home/user/SyftBox")
        PosixPath('/home/user/SyftBox/datasites/user/data')

        >>> os.environ['SYFTBOX_FOLDER'] = '/home/user/SyftBox'
        >>> resolve_path("syft://apps/myapp")
        PosixPath('/home/user/SyftBox/apps/myapp')
    """
    # Convert path to string for processing
    # Handle case where Path object might normalize syft:// to syft:/
    if isinstance(path, Path):
        path_str = str(path)
        # Fix Path normalization of syft:// -> syft:/
        if path_str.startswith("syft:/") and not path_str.startswith("syft://"):
            path_str = path_str.replace("syft:/", "syft://", 1)
    else:
        path_str = str(path)

    # Check if path starts with syft://
    if not path_str.startswith("syft://"):
        raise ValueError(f"Path must start with 'syft://', got: {path_str}")

    # Determine syftbox folder
    if syftbox_folder is not None:
        base_folder = Path(syftbox_folder)
    else:
        env_folder = os.environ.get("SYFTBOX_FOLDER")
        if env_folder is None:
            raise ValueError(
                "SYFTBOX_FOLDER environment variable not set. "
                "Please either:\n"
                "1. Set the environment variable: export SYFTBOX_FOLDER=/path/to/syftbox\n"
                "2. Pass syftbox_folder parameter: resolve_path(path, syftbox_folder='/path/to/syftbox')"
            )
        base_folder = Path(env_folder)

    # Remove syft:// prefix and resolve path
    relative_path = path_str[7:]  # Remove "syft://" (7 characters)

    # Handle empty path after syft://
    if not relative_path:
        return base_folder

    # Join with base folder and return
    return base_folder / relative_path
