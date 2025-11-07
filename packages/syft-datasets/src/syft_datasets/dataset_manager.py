import re
import shutil
from pathlib import Path
from typing import Self

from .types import PathLike, to_path
from syft_notebook_ui.types import TableList
from typing_extensions import Literal

from syft_datasets.dataset import Dataset, PrivateDatasetConfig
from syft_datasets.file_utils import copy_dir_contents, copy_paths, is_empty_dir

from .url import SyftBoxURL
from .config import SyftBoxConfig

FOLDER_NAME = "syft_datasets"
METADATA_FILENAME = "dataset.yaml"


class SyftDatasetManager:
    def __init__(self, syftbox_folder_path: PathLike, email: str):
        self.syftbox_config = SyftBoxConfig(
            syftbox_folder=to_path(syftbox_folder_path), email=email
        )

    @classmethod
    def from_config(cls, config: SyftBoxConfig) -> Self:
        return cls(syftbox_folder_path=config.syftbox_folder, email=config.email)

    def public_dir_for_datasite(self, datasite: str) -> Path:
        dir = self.syftbox_config.syftbox_folder / datasite / "public" / FOLDER_NAME
        dir.mkdir(parents=True, exist_ok=True)
        return dir

    def get_mock_dataset_dir(self, dataset_name: str, datasite: str) -> Path:
        return self.public_dir_for_datasite(datasite) / dataset_name

    def _validate_dataset_name(self, dataset_name: str) -> None:
        # Returns True if the dataset is a valid path name on unix or windows.
        if not re.match(r"^[\w-]+$", dataset_name):
            raise ValueError(
                f"Invalid dataset name '{dataset_name}'. Only alphanumeric characters, underscores, and hyphens are allowed."
            )

    def _prepare_mock_data(self, dataset: Dataset, src_path: Path) -> None:
        # Validate src data
        if not src_path.exists():
            raise FileNotFoundError(f"Could not find mock data at {src_path}")

        if (src_path / METADATA_FILENAME).exists():
            raise ValueError(
                f"Mock data at {src_path} contains reserved file {METADATA_FILENAME}. Please rename it and try again."
            )

        # Validate dir we're making on Syftbox
        if dataset.mock_dir.exists() and not is_empty_dir(dataset.mock_dir):
            raise FileExistsError(
                f"Mock dir {dataset.mock_dir} already exists and is not empty."
            )
        dataset.mock_dir.mkdir(parents=True, exist_ok=True)

        if src_path.is_dir():
            copy_dir_contents(
                src=src_path,
                dst=dataset.mock_dir,
                exists_ok=True,
            )
        elif src_path.is_file():
            copy_paths(
                files=[src_path],
                dst=dataset.mock_dir,
                exists_ok=True,
            )
        else:
            raise ValueError(
                f"Mock data path {src_path} must be an existing file or directory."
            )

    def _prepare_private_data(
        self,
        dataset: Dataset,
        src_path: Path,
    ) -> None:
        dataset.private_dir.mkdir(parents=True, exist_ok=True)

        if src_path.is_dir():
            # TODO: Implementing without copying private data to `SyftBox/private``
            copy_dir_contents(
                src=src_path,
                dst=dataset.private_dir,
                exists_ok=True,
            )
        elif src_path.is_file():
            copy_paths(
                files=[src_path],
                dst=dataset.private_dir,
                exists_ok=True,
            )
        else:
            raise ValueError(
                f"Private data path {src_path} must be an existing file or directory."
            )

    def _prepare_private_config(
        self,
        dataset: Dataset,
        private_data_dir: Path,
        location: str | None = None,
    ) -> None:
        """
        The private dataset config is used to store private metadata separately from the public dataset metadata.
        """
        if dataset._private_metadata_dir.exists() and not is_empty_dir(
            dataset._private_metadata_dir
        ):
            raise FileExistsError(
                f"Private dir {dataset.private_dir} already exists and is not empty."
            )

        private_config = PrivateDatasetConfig(
            uid=dataset.uid,
            data_dir=private_data_dir,
            location=location,
        )

        private_config_path = dataset.private_config_path
        private_config_path.parent.mkdir(parents=True, exist_ok=True)
        private_config.save(filepath=private_config_path)

    def _prepare_readme(self, dataset: Dataset, src_file: Path | None) -> None:
        if src_file is not None:
            if not src_file.is_file():
                raise FileNotFoundError(f"Could not find README at {src_file}")
            if not src_file.suffix.lower() == ".md":
                raise ValueError("readme file must be a markdown (.md) file.")
            copy_paths(
                files=[src_file],
                dst=dataset.mock_dir,
                exists_ok=True,
            )

    def create(
        self,
        name: str,
        mock_path: PathLike,
        private_path: PathLike,
        summary: str | None = None,
        readme_path: Path | None = None,
        location: str | None = None,
        tags: list[str] | None = None,
        # copy_private_data: bool = True, # TODO
    ) -> Dataset:
        """_summary_

        Args:
            name (str): Unique of the dataset to create.
            mock_path (PathLike): Path to the existing mock data. This can be a file or a directory.
            private_path (PathLike): Path to the existing private data. This can be a file or a directory.
            summary (str | None, optional): Short summary of the dataset. Defaults to None.
            readme_path (Path | None, optional): Markdown README in the public dataset. Defaults to None.
            location (str | None, optional): Location identifier for the dataset, e.g. 'high-side-1234'.
                Only required for datasets that are hosted on a remote location and require manual syncing.
                Defaults to None.
            tags (list[str] | None, optional): Optional tags for the dataset. Defaults to None.

        Returns:
            Dataset: The created Dataset object.
        """
        mock_path = to_path(mock_path)
        private_path = to_path(private_path)
        readme_path = to_path(readme_path) if readme_path else None
        tags = tags or []

        mock_dir = self.get_mock_dataset_dir(
            dataset_name=name,
            datasite=self.syftbox_config.email,
        )
        mock_url = SyftBoxURL.from_path(
            path=mock_dir,
            syftbox_folder=self.syftbox_config.syftbox_folder,
        )
        readme_url = None
        if readme_path:
            readme_url = SyftBoxURL.from_path(
                path=mock_dir / readme_path.name,
                syftbox_folder=self.syftbox_config.syftbox_folder,
            )

        dataset = Dataset(
            name=name,
            mock_url=mock_url,
            readme_url=readme_url,
            summary=summary,
            location=location,
            tags=tags,
        )
        dataset._syftbox_config = self.syftbox_config

        self._prepare_mock_data(
            dataset=dataset,
            src_path=mock_path,
        )
        self._prepare_readme(
            dataset=dataset,
            src_file=readme_path,
        )

        # TODO enable adding private data without copying to SyftBox
        # e.g. private_data_dir = dataset._private_metadata_dir if copy_private_data else private_path
        self._prepare_private_config(
            dataset=dataset,
            private_data_dir=dataset._private_metadata_dir,
        )
        self._prepare_private_data(
            dataset=dataset,
            src_path=private_path,
        )

        dataset_yaml_path = mock_dir / METADATA_FILENAME
        dataset.save(filepath=dataset_yaml_path)
        return dataset

    def _load_dataset_from_dir(self, dataset_dir: Path) -> Dataset:
        metadata_path = dataset_dir / METADATA_FILENAME
        if not metadata_path.exists():
            raise FileNotFoundError(f"Dataset metadata not found at {metadata_path}")

        return Dataset.load(
            filepath=metadata_path,
            syftbox_config=self.syftbox_config,
        )

    def get(self, name: str, datasite: str | None = None) -> Dataset:
        datasite = datasite or self.syftbox_config.email
        mock_dir = self.get_mock_dataset_dir(
            dataset_name=name,
            datasite=datasite,
        )

        if not mock_dir.exists():
            raise FileNotFoundError(f"Dataset {name} not found in {mock_dir}")
        return self._load_dataset_from_dir(mock_dir)

    def __getitem__(self, key: str) -> Dataset:
        return self.get(name=key)

    def get_all(
        self,
        datasite: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
        order_by: str | None = None,
        sort_order: Literal["asc", "desc"] = "asc",
    ) -> list[Dataset]:
        all_datasets = []

        if datasite:
            datasites_to_check = [datasite]
        else:
            syftbox_folder = self.syftbox_config.syftbox_folder
            # All directories with "@" in the name are peer/owner email directories
            datasites_to_check = [
                d.name for d in syftbox_folder.iterdir() if d.is_dir() and "@" in d.name
            ]

        for datasite in datasites_to_check:
            public_datasets_dir = self.public_dir_for_datasite(datasite)
            if not public_datasets_dir.exists():
                continue
            for dataset_dir in public_datasets_dir.iterdir():
                if dataset_dir.is_dir():
                    try:
                        dataset = self._load_dataset_from_dir(dataset_dir)
                        all_datasets.append(dataset)
                    except Exception:
                        continue

        if order_by is not None:
            all_datasets.sort(
                key=lambda d: getattr(d, order_by),
                reverse=(sort_order.lower() == "desc"),
            )

        if offset is not None:
            all_datasets = all_datasets[offset:]
        if limit is not None:
            all_datasets = all_datasets[:limit]

        return TableList(all_datasets)

    def delete(
        self,
        name: str,
        datasite: str | None = None,
        require_confirmation: bool = True,
    ) -> None:
        datasite = datasite or self.syftbox_config.email

        if datasite != self.syftbox_config.email:
            # NOTE this check is easily bypassed, but bypassing does not have any effect.
            # When bypassed, the dataset will be restored because the user only has
            # read access to someone else's datasite.
            raise ValueError(
                "Cannot delete datasets from a datasite that is not your own."
            )

        try:
            dataset = self.get(
                name=name,
                datasite=datasite,
            )
        except FileNotFoundError:
            raise FileNotFoundError(f"Dataset {name} not found in datasite {datasite}")

        if require_confirmation:
            msg = (
                "Deleting this dataset will remove the following folders:\n"
                f"Mock data: {dataset.mock_dir}\n"
                f"Private metadata: {dataset._private_metadata_dir}\n"
            )
            if (
                dataset.private_dir.resolve().absolute()
                == dataset._private_metadata_dir.resolve().absolute()
            ):
                msg += (
                    "WARNING: this will also delete the private data from your system\n"
                )
            else:
                msg += "Private data will not be deleted from your system, it is not managed by SyftBox.\n"

            msg += "Are you sure you want to delete these folders? (yes/no): "
            confirmation = input(msg).strip().lower()
            if confirmation != "yes":
                print("Dataset deletion cancelled.")
                return

        # Delete the dataset directories
        if dataset.mock_dir.exists():
            shutil.rmtree(dataset.mock_dir)
        if dataset._private_metadata_dir.exists():
            shutil.rmtree(dataset._private_metadata_dir)
