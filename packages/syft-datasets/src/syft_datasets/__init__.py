from .types import PathLike
from typing_extensions import Literal

from syft_datasets.dataset import Dataset
from syft_datasets.dataset_manager import SyftDatasetManager


def create(
    name: str,
    mock_path: PathLike,
    private_path: PathLike,
    summary: str | None = None,
    readme_path: PathLike | None = None,
    location: str | None = None,
    tags: list[str] | None = None,
    syftbox_config_path: PathLike | None = None,
) -> Dataset:
    dataset_manager = SyftDatasetManager.load(config_path=syftbox_config_path)
    return dataset_manager.create(
        name=name,
        mock_path=mock_path,
        private_path=private_path,
        summary=summary,
        readme_path=readme_path,
        location=location,
        tags=tags,
    )


def get(
    name: str,
    datasite: str | None = None,
    syftbox_config_path: PathLike | None = None,
) -> Dataset:
    dataset_manager = SyftDatasetManager.load(config_path=syftbox_config_path)
    return dataset_manager.get(name=name, datasite=datasite)


def get_all(
    datasite: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = None,
    sort_order: Literal["asc", "desc"] = "asc",
    syftbox_config_path: PathLike | None = None,
) -> list[Dataset]:
    dataset_manager = SyftDatasetManager.load(config_path=syftbox_config_path)
    return dataset_manager.get_all(
        datasite,
        limit,
        offset,
        order_by,
        sort_order,
    )


def delete(
    name: str,
    datasite: str | None = None,
    syftbox_config_path: PathLike | None = None,
) -> None:
    dataset_manager = SyftDatasetManager.load(config_path=syftbox_config_path)
    return dataset_manager.delete(name=name, datasite=datasite)
