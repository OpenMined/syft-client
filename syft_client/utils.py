from pathlib import Path
import os
from typing import Optional, Union
from typing_extensions import TYPE_CHECKING

from syft_datasets.dataset_manager import SyftDatasetManager

if TYPE_CHECKING:
    from syft_client.sync.syftbox_manager import SyftBoxManager


def resolve_dataset_file_path(*args, **kwargs):
    return resolve_dataset_files_path(*args, **kwargs)[0]


def get_syftbox_folder_if_not_passed(
    syftbox_folder: Optional[Union[str, Path]] = None,
) -> Path:
    if syftbox_folder is not None:
        syftbox_folder = Path(syftbox_folder)
    else:
        env_folder = os.environ.get("SYFTBOX_FOLDER")
        if env_folder is None:
            raise ValueError(
                "SYFTBOX_FOLDER environment variable not set. "
                "Please either:\n"
                "1. Set the environment variable: export SYFTBOX_FOLDER=/path/to/syftbox\n"
                "2. Pass syftbox_folder parameter: resolve_path(path, syftbox_folder='/path/to/syftbox')"
            )
        syftbox_folder = Path(env_folder)
    return syftbox_folder


def validate_owner_email(owner_emails: list[str], dataset_name: str) -> str:
    if len(owner_emails) == 1:
        return owner_emails[0]
    else:
        if len(owner_emails) == 0:
            raise ValueError(
                f"No datasets with name {dataset_name} found, please create a dataset first"
            )
        else:
            raise ValueError(
                f"{len(owner_emails)} datasets with name {dataset_name} found, please specify the owner_email"
            )


def resolve_dataset_files_path(
    dataset_name: str,
    syftbox_folder: Optional[Union[str, Path]] = None,
    owner_email: Optional[str] = None,
    client: Optional["SyftBoxManager"] = None,
) -> Path:
    if syftbox_folder is None and client is not None:
        syftbox_folder = client.dataset_manager.syftbox_config.syftbox_folder

    syftbox_folder = get_syftbox_folder_if_not_passed(syftbox_folder)

    if owner_email is None and client is not None:
        owner_emails = client._resolve_dataset_owners_for_name(dataset_name)
        owner_email = validate_owner_email(owner_emails, dataset_name)
    owner = owner_email or os.environ.get("SYFTBOX_EMAIL")
    if owner is None:
        raise ValueError(
            "Owner email not provided and SYFTBOX_EMAIL environment variable not set. Please provide the owner_email parameter or set the SYFT_EMAIL environment variable."
        )

    use_private = os.environ.get("SYFT_IS_IN_JOB", "false").lower() == "true"

    # we dont use the email so we can use ""
    manager = SyftDatasetManager(syftbox_folder_path=syftbox_folder, email="")
    dataset = manager.get(name=dataset_name, datasite=owner)
    if use_private:
        return dataset.private_files
    else:
        return dataset.mock_files


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
    syftbox_folder = get_syftbox_folder_if_not_passed(syftbox_folder)

    # Remove syft:// prefix and resolve path
    relative_path = path_str[7:]  # Remove "syft://" (7 characters)

    # Handle empty path after syft://
    if not relative_path:
        return syftbox_folder

    # Join with base folder and return
    return syftbox_folder / relative_path
