from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from .job_repr import (
    StderrViewer,
    job_info_repr_html,
    jobs_list_repr_html,
    jobs_list_str,
)
from .job_stdout import StdoutViewer

if TYPE_CHECKING:
    from .client import JobClient


class JobInfo:
    """Information about a job with approval capabilities."""

    def __init__(
        self,
        name: str,
        datasite_owner_email: str,
        status: str,
        submitted_by: str,
        location: Path,
        client: JobClient,
        current_user_email: str,
        submitted_at: Optional[str] = None,
    ):
        self.name = name
        self.datasite_owner_email = datasite_owner_email
        self.status = status
        self.submitted_by = submitted_by
        self.location = location
        self._client = client
        self.current_user_email = current_user_email
        self.submitted_at = submitted_at

    def __str__(self) -> str:
        status_emojis = {"inbox": "📥", "approved": "✅", "done": "🎉"}
        emoji = status_emojis.get(self.status, "❓")
        return f"{emoji} {self.name} ({self.status}) -> {self.datasite_owner_email}"

    def __repr__(self) -> str:
        return f"JobInfo(name='{self.name}', submitted_by='{self.submitted_by}', current_user_email='{self.current_user_email}', status='{self.status}')"

    def accept_by_depositing_result(self, path: str) -> Path:
        """
        Accept a job by depositing the result file or folder and creating done marker.

        Args:
            path: Path to the result file or folder to deposit

        Returns:
            Path to the deposited result file or folder in the outputs directory

        Raises:
            ValueError: If job is not in inbox or approved status
            FileNotFoundError: If the result file or folder doesn't exist
        """
        if self.status not in ["inbox", "approved"]:
            raise ValueError(
                f"Job '{self.name}' is not in inbox or approved status (current: {self.status})"
            )

        result_path = Path(path)
        if not result_path.exists():
            raise FileNotFoundError(f"Result path not found: {path}")

        # Create outputs directory in the job directory
        outputs_dir = self.location / "outputs"
        outputs_dir.mkdir(exist_ok=True)

        # Handle both files and folders
        result_name = result_path.name
        destination = outputs_dir / result_name

        if result_path.is_file():
            shutil.copy2(str(result_path), str(destination))
        elif result_path.is_dir():
            shutil.copytree(str(result_path), str(destination))
        else:
            raise ValueError(f"Path is neither a file nor a directory: {path}")

        # Create done marker file (this also creates approved marker if not present)
        self._client.create_approved_marker(self.location)
        self._client.create_done_marker(self.location)

        self.status = "done"

        print(
            f"✅ Job '{self.name}' completed successfully! Result deposited at: {destination}"
        )

        return destination

    def approve(self) -> None:
        """
        Approve a job by creating approved marker file.
        Only the admin user can approve jobs in their own folder.

        Raises:
            ValueError: If job is not in inbox status
            PermissionError: If the current user is not authorized to approve jobs
        """
        if self.status != "inbox":
            raise ValueError(
                f"Job '{self.name}' is not in inbox status (current: {self.status})"
            )

        if self.datasite_owner_email != self.current_user_email:
            raise PermissionError(
                f"Only the admin user ({self.datasite_owner_email}) can approve jobs in their folder. "
                f"Current job is in {self.datasite_owner_email}'s folder."
            )

        self._client.create_approved_marker(self.location)
        self.status = "approved"
        print(f"✅ Job '{self.name}' approved successfully!")

    @property
    def output_paths(self) -> List[Path]:
        """
        Get list of all file paths in the outputs directory for done jobs.

        Returns:
            List of Path objects for all files/directories in outputs folder.
            Empty list if job is not done or outputs directory doesn't exist.
        """
        if self.status != "done":
            return []

        outputs_dir = self.location / "outputs"
        if not outputs_dir.exists():
            return []

        try:
            return [item for item in outputs_dir.iterdir()]
        except Exception:
            return []

    @property
    def stdout(self) -> StdoutViewer:
        """Get a viewer for the stdout content for completed jobs."""
        return StdoutViewer(self)

    @property
    def stderr(self) -> StderrViewer:
        """Get a viewer for the stderr content for completed jobs."""
        return StderrViewer(self)

    def rerun(self) -> None:
        """
        Rerun a job by removing logs, outputs, and done marker file.

        Raises:
            ValueError: If job is not in done status
        """
        if self.status != "done":
            raise ValueError(
                f"Job '{self.name}' is not in done status (current: {self.status}). "
                f"Only completed jobs can be rerun."
            )

        changes_made = []

        logs_dir = self.location / "logs"
        if logs_dir.exists() and logs_dir.is_dir():
            shutil.rmtree(logs_dir)
            changes_made.append("logs directory")

        outputs_dir = self.location / "outputs"
        if outputs_dir.exists() and outputs_dir.is_dir():
            shutil.rmtree(outputs_dir)
            changes_made.append("outputs directory")

        done_file = self.location / "done"
        if done_file.exists():
            done_file.unlink()
            changes_made.append("done marker file")

        self.status = "approved"

        if changes_made:
            print(
                f"🔄 Job '{self.name}' prepared for rerun! Removed: {', '.join(changes_made)}"
            )
        else:
            print(f"🔄 Job '{self.name}' prepared for rerun! (No cleanup needed)")

    @property
    def files(self) -> List[Path]:
        """
        Get list of all file paths in the job folder.

        Returns:
            List of Path objects for all files and directories in the job folder.
            Empty list if job folder doesn't exist or can't be accessed.
        """
        try:
            if not self.location.exists():
                return []
            return [item for item in self.location.iterdir()]
        except Exception:
            return []

    def _get_perm_context(self):
        from syft_perm import SyftPermContext

        datasite = self._client.config.syftbox_folder / self.datasite_owner_email
        return SyftPermContext(datasite=datasite)

    def _path_in_datasite(self, subpath: str) -> str:
        """Return path relative to the datasite for a job subpath."""
        rel = self.location.relative_to(
            self._client.config.syftbox_folder / self.datasite_owner_email
        )
        return str(rel / subpath)

    def share_outputs(self, users: list[str]) -> None:
        """Grant read access to the outputs directory for given users."""
        ctx = self._get_perm_context()
        outputs_rel = self._path_in_datasite("outputs") + "/"
        folder = ctx.open(outputs_rel)
        for user in users:
            folder.grant_read_access(user)

    def share_logs(self, users: list[str]) -> None:
        """Grant read access to log files (stdout, stderr, returncode) for given users."""
        ctx = self._get_perm_context()
        for filename in ("stdout.txt", "stderr.txt", "returncode.txt"):
            file_rel = self._path_in_datasite(filename)
            f = ctx.open(file_rel)
            for user in users:
                f.grant_read_access(user)

    def _repr_html_(self) -> str:
        return job_info_repr_html(self)


class JobsList:
    """A list-like container for JobInfo objects with nice display."""

    def __init__(self, jobs: List[JobInfo], root_email: str):
        self._jobs = jobs
        self._root_email = root_email

    def __getitem__(self, index: int | str) -> JobInfo:
        if isinstance(index, int):
            return self._jobs[index]
        elif isinstance(index, str):
            for job in self._jobs:
                if job.name == index:
                    return job
            raise ValueError(f"Job with name '{index}' not found")
        else:
            raise TypeError(f"Invalid index type: {type(index)}")

    def __len__(self) -> int:
        return len(self._jobs)

    def __iter__(self):
        return iter(self._jobs)

    def __str__(self) -> str:
        return jobs_list_str(self._jobs, self._root_email)

    def __repr__(self) -> str:
        return f"JobsList({len(self._jobs)} jobs)"

    def _repr_html_(self) -> str:
        return jobs_list_repr_html(self._jobs, self._root_email)
