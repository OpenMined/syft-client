import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from syft_perm.syftperm_context import SyftPermContext
import yaml

from .config import SyftJobConfig
from .install_source import get_syft_client_install_source
from .job import JobInfo, JobsList

# Python version used when creating virtual environments for job execution
RUN_SCRIPT_PYTHON_VERSION = "3.12"


class JobClient:
    """Client for submitting jobs to SyftBox."""

    def __init__(
        self, config: SyftJobConfig, target_datasite_owner_email: Optional[str] = None
    ):
        """Initialize JobClient with configuration and optional user email for job views."""
        self.config = config
        self.current_user_email = (
            config.email
        )  # From SyftBox folder (for "submitted_by")
        self.target_datasite_owner_email = (
            target_datasite_owner_email or config.email
        )  # The email of the datasite owner of the jobs

        # Validate that user_email exists in SyftBox root
        self._validate_user_email()

    @classmethod
    def from_config(cls, config: SyftJobConfig) -> "JobClient":
        return cls(config, config.email)

    def _validate_user_email(self) -> None:
        """Validate that the user_email directory exists in SyftBox root."""
        user_dir = self.config.get_user_dir(self.target_datasite_owner_email)
        if not user_dir.exists():
            # Create user directory if it doesn't exist
            user_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created user directory: {user_dir}")

    def get_job_status(self, job_path: Path) -> str:
        """Get the status of a job based on marker files."""
        if not job_path.is_dir():
            raise ValueError(f"Job path is not a directory: {job_path}")
        if (job_path / "done").exists():
            return "done"
        elif (job_path / "approved").exists():
            return "approved"
        return "inbox"

    def create_approved_marker(self, job_path: Path) -> None:
        """Create approved marker file in job directory."""
        (job_path / "approved").touch()

    def create_done_marker(self, job_path: Path) -> None:
        """Create done marker file in job directory."""
        (job_path / "done").touch()

    def is_job_approved(self, job_path: Path) -> bool:
        """Check if job has been approved (has approved file)."""
        return (job_path / "approved").exists()

    def is_job_done(self, job_path: Path) -> bool:
        """Check if job has been completed (has done file)."""
        return (job_path / "done").exists()

    def is_job_inbox(self, job_path: Path) -> bool:
        """Check if job is still in inbox (no status markers)."""
        return not self.is_job_approved(job_path) and not self.is_job_done(job_path)

    def _get_job_dir_for_me(self, target_datasite_owner_email: str) -> Path:
        return (
            self.config.get_job_dir(target_datasite_owner_email)
            / self.current_user_email
        )

    def _ensure_my_job_directory_exists(self, target_datasite_owner_email: str) -> None:
        """Ensure job directory structure exists for a user, including DS subdirectory."""
        ds_job_dir = self._get_job_dir_for_me(target_datasite_owner_email)
        ds_job_dir.mkdir(parents=True, exist_ok=True)

    def setup_ds_job_folder_as_do(self, ds_email: str) -> Path:
        """Create a DS-specific job subdirectory with write permissions for that DS.

        Args:
            ds_email: Email of the data scientist to create the folder for.

        Returns:
            Path to the created DS job folder.
        """
        ds_job_dir = self.config.get_job_dir(self.current_user_email) / ds_email
        ds_job_dir.mkdir(parents=True, exist_ok=True)
        datasite = self.config.syftbox_folder / self.current_user_email

        ctx = SyftPermContext(datasite=datasite)
        rel_path = str(ds_job_dir.relative_to(datasite)) + "/"
        ctx.open(rel_path).grant_write_access(ds_email)
        return ds_job_dir

    def submit_bash_job(self, user: str, script: str, job_name: str = "") -> Path:
        """
        Submit a bash job for a user.

        Args:
            user: Email address of the user to submit job for
            script: Bash script content to execute
            job_name: Name of the job (will be used as directory name). If empty, defaults to "Job - <random_id>"

        Returns:
            Path to the created job directory

        Raises:
            FileExistsError: If job with same name already exists
            ValueError: If user directory doesn't exist
        """
        submitting_to_email = user
        # Generate default job name if not provided
        if not job_name.strip():
            from uuid import uuid4

            random_id = str(uuid4())[0:8]
            job_name = f"Job - {random_id}"
        # Ensure user directory exists (create if it doesn't)
        user_dir = self.config.get_user_dir(user)
        if not user_dir.exists():
            user_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created user directory: {user_dir}")

        # Ensure job directory structure exists
        self._ensure_my_job_directory_exists(submitting_to_email)

        # Create job directory under DS email subdirectory
        job_dir = self._get_job_dir_for_me(submitting_to_email) / job_name

        if job_dir.exists():
            raise FileExistsError(
                f"Job '{job_name}' already exists for user '{submitting_to_email}'"
            )

        job_dir.mkdir(parents=True)

        # Create run.sh file
        run_script_path = job_dir / "run.sh"
        with open(run_script_path, "w") as f:
            f.write(script)

        # Make run.sh executable
        os.chmod(run_script_path, 0o755)

        # Create config.yaml file
        config_yaml_path = job_dir / "config.yaml"
        from datetime import datetime, timezone

        job_config = {
            "name": job_name,
            "submitted_by": self.current_user_email,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        with open(config_yaml_path, "w") as f:
            yaml.dump(job_config, f, default_flow_style=False)

        return job_dir

    def _detect_entrypoint(self, folder_path: Path) -> Optional[str]:
        """Auto-detect entrypoint for folder submissions.

        Detection priority:
        1. main.py - most common convention
        2. Single .py file at root - if only one exists

        Args:
            folder_path: Path to the folder to search

        Returns:
            Detected entrypoint filename or None if not found
        """
        # Check main.py first (most common convention)
        if (folder_path / "main.py").exists():
            return "main.py"

        # Check for single .py file at root
        py_files = [
            f for f in folder_path.iterdir() if f.is_file() and f.suffix == ".py"
        ]
        if len(py_files) == 1:
            return py_files[0].name

        return None

    def _validate_code_path_and_entrypoint(
        self, code_path: str, entrypoint: Optional[str]
    ) -> Tuple[Path, bool, str]:
        """
        Validate code path and entrypoint for Python job submission.

        Args:
            code_path: Path to Python file or folder
            entrypoint: Entry point file name (auto-detected if not provided)

        Returns:
            Tuple of (resolved_code_path, is_folder_submission, validated_entrypoint)

        Raises:
            FileNotFoundError: If code_path doesn't exist
            ValueError: If validation fails
        """
        code_path_input = code_path  # Keep original for error messages
        resolved_path = Path(code_path).expanduser().resolve()

        if not resolved_path.exists():
            raise FileNotFoundError(f"Code path does not exist: {code_path_input}")

        is_folder_submission = resolved_path.is_dir()

        if is_folder_submission:
            if not entrypoint:
                # Auto-detect entrypoint
                entrypoint = self._detect_entrypoint(resolved_path)
                if not entrypoint:
                    raise ValueError(
                        "Could not auto-detect entrypoint. No main.py or single .py file "
                        "found at folder root. Please specify the entrypoint explicitly."
                    )

            entrypoint_path = resolved_path / entrypoint
            if not entrypoint_path.exists() or not entrypoint_path.is_file():
                raise ValueError(
                    f"Entrypoint file '{entrypoint}' not found in folder: {code_path_input}"
                )

            if entrypoint_path.suffix != ".py":
                raise ValueError(
                    f"Entrypoint file must be a Python file (.py): {entrypoint}"
                )
        else:
            if resolved_path.suffix != ".py":
                raise ValueError(
                    f"Code path must be a Python file (.py): {code_path_input}"
                )
            # Auto-detect entrypoint for file submissions
            entrypoint = resolved_path.name

        return resolved_path, is_folder_submission, entrypoint

    def _generate_python_run_script(
        self, entrypoint_path: str, dependencies: List[str], has_pyproject: bool
    ) -> str:
        """
        Generate bash script for Python job execution.

        Args:
            entrypoint_path: Path to Python file to execute (e.g., "script.py" or "project_dir/main.py")
            dependencies: List of dependencies to install
            has_pyproject: Whether the code has a pyproject.toml

        Returns:
            Bash script content
        """
        all_dependencies = [get_syft_client_install_source()] + dependencies

        if has_pyproject:
            # For projects with pyproject.toml, run uv sync inside the project folder
            # entrypoint_path is like "project_dir/main.py", so folder is the first part
            code_folder = entrypoint_path.split("/")[0]
            # Always install syft_client (and any extra dependencies) after uv sync
            deps_str = " ".join(f'"{dep}"' for dep in all_dependencies)
            install_deps_cmd = f"uv pip install {deps_str}"

            return f"""#!/bin/bash
set -euo pipefail
export UV_SYSTEM_PYTHON=false
cd {code_folder} && uv sync --python {RUN_SCRIPT_PYTHON_VERSION} && cd ..
source {code_folder}/.venv/bin/activate
{install_deps_cmd}
export PYTHONPATH={code_folder}:${{PYTHONPATH:-}}
python {entrypoint_path}
"""
        else:
            # For folder submissions without pyproject.toml, add code folder to PYTHONPATH
            # entrypoint_path is like "project_dir/main.py" for folders, or "script.py" for single files
            code_folder = (
                entrypoint_path.split("/")[0] if "/" in entrypoint_path else ""
            )
            pythonpath_cmd = (
                f"export PYTHONPATH={code_folder}:${{PYTHONPATH:-}}"
                if code_folder
                else ""
            )

            deps_str = " ".join(f'"{dep}"' for dep in all_dependencies)
            return f"""#!/bin/bash
set -euo pipefail
export UV_SYSTEM_PYTHON=false
uv venv --python {RUN_SCRIPT_PYTHON_VERSION}
source .venv/bin/activate
uv pip install {deps_str}
{pythonpath_cmd}
python {entrypoint_path}
"""

    def submit_python_job(
        self,
        user: str,
        code_path: str,
        job_name: Optional[str] = "",
        dependencies: Optional[List[str]] = None,
        entrypoint: Optional[str] = None,
    ) -> Path:
        """
        Submit a Python job for a user (supports both files and folders).

        Args:
            user: Email address of the user to submit job for
            job_name: Name of the job (will be used as directory name)
            code_path: Path to Python file or folder containing Python code
            dependencies: List of Python packages to install (e.g., ["numpy", "pandas==1.5.0"])
            entrypoint: Entry point file name for folder submissions (mandatory for folders, auto-detected for files)

        Returns:
            Path to the created job directory

        Raises:
            FileExistsError: If job with same name already exists
            ValueError: If code_path validation fails or entrypoint is missing for folders
            FileNotFoundError: If code_path doesn't exist
        """
        submitting_to_email = user
        # Generate default job name if not provided
        if not job_name:
            from uuid import uuid4

            random_id = str(uuid4())[0:8]
            job_name = f"Job - {random_id}"

        # Validate code path and entrypoint
        code_path, is_folder_submission, entrypoint = (
            self._validate_code_path_and_entrypoint(code_path, entrypoint)
        )

        # Ensure user directory exists (create if it doesn't)
        user_dir = self.config.get_user_dir(user)
        if not user_dir.exists():
            user_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created user directory: {user_dir}")

        # Ensure job directory structure exists
        self._ensure_my_job_directory_exists(submitting_to_email)

        # Create job directory under DS email subdirectory
        job_dir = self._get_job_dir_for_me(submitting_to_email) / job_name

        if job_dir.exists():
            raise FileExistsError(f"Job '{job_name}' already exists for user '{user}'")

        job_dir.mkdir(parents=True)

        # Copy code to job directory
        if is_folder_submission:
            # Copy entire folder (preserving folder name) to job directory
            # e.g., project_dir/ -> job_dir/project_dir/
            code_folder_name = code_path.name
            shutil.copytree(code_path, job_dir / code_folder_name)
            # Entrypoint path includes folder name
            entrypoint_path = f"{code_folder_name}/{entrypoint}"
            pyproject_path = job_dir / code_folder_name / "pyproject.toml"
        else:
            # Copy single Python file to job directory
            shutil.copy2(code_path, job_dir / code_path.name)
            entrypoint_path = entrypoint
            pyproject_path = None

        # Generate bash script for Python execution
        dependencies = dependencies or []
        has_pyproject = pyproject_path is not None and pyproject_path.exists()
        bash_script = self._generate_python_run_script(
            entrypoint_path, dependencies, has_pyproject
        )

        # Compute all_dependencies for config.yaml
        all_dependencies = [get_syft_client_install_source()] + dependencies

        # Create run.sh file
        run_script_path = job_dir / "run.sh"
        with open(run_script_path, "w") as f:
            f.write(bash_script)

        # Make run.sh executable
        os.chmod(run_script_path, 0o755)

        # Create config.yaml file
        config_yaml_path = job_dir / "config.yaml"
        from datetime import datetime, timezone

        job_config = {
            "name": job_name,
            "submitted_by": self.current_user_email,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "type": "python",
            "code_path": str(code_path),
            "entry_point": entrypoint,
            "dependencies": all_dependencies,
            "is_folder_submission": is_folder_submission,
        }

        with open(config_yaml_path, "w") as f:
            yaml.dump(job_config, f, default_flow_style=False)

        return job_dir

    def _get_all_jobs(self) -> List[JobInfo]:
        """Get all jobs from all peer directories (inbox, approved, done)."""
        jobs: list[JobInfo] = []
        syftbox_root = self.config.syftbox_folder

        if not syftbox_root.exists():
            return jobs

        # Scan through all user directories in SyftBox root (peers)
        for datasite_owner_dir in syftbox_root.iterdir():
            if not datasite_owner_dir.is_dir():
                continue

            datasite_owner_email = datasite_owner_dir.name
            datasite_owner_job_dir = self.config.get_job_dir(datasite_owner_email)

            if not datasite_owner_job_dir.exists():
                continue

            # Scan DS subdirectories, then job directories within each
            for ds_dir in datasite_owner_job_dir.iterdir():
                if not ds_dir.is_dir():
                    continue

                for job_dir in ds_dir.iterdir():
                    if not job_dir.is_dir():
                        continue

                    config_file = job_dir / "config.yaml"
                    if not config_file.exists():
                        continue

                    try:
                        with open(config_file, "r") as f:
                            job_config = yaml.safe_load(f)

                        status = self.get_job_status(job_dir)

                        jobs.append(
                            JobInfo(
                                name=job_config.get("name", job_dir.name),
                                datasite_owner_email=datasite_owner_email,
                                status=status,
                                submitted_by=job_config.get("submitted_by", "unknown"),
                                location=job_dir,
                                client=self,
                                current_user_email=self.current_user_email,
                                submitted_at=job_config.get("submitted_at"),
                            )
                        )
                    except Exception:
                        continue

        return jobs

    @property
    def jobs(self) -> JobsList:
        """
        Get all jobs from all peer directories as an indexable list grouped by user.

        Returns a JobsList object that can be:
        - Indexed: jobs[0], jobs[1], etc.
        - Iterated: for job in jobs
        - Displayed: print(jobs) shows separate tables for each user
        - HTML display: in Jupyter, shows separate tables for each user with jobs

        Each job has an accept_by_depositing_result() method for approval.
        Only displays users that have jobs (skips empty peer directories).

        Returns:
            JobsList containing all jobs from all peer directories, grouped by user
        """
        current_jobs = self._get_all_jobs()

        # Sort jobs by recent submissions first (newest first), then by user/status
        def job_sort_key(job):
            # Parse submitted_at timestamp for sorting (most recent first)
            try:
                if job.submitted_at:
                    from datetime import datetime

                    # Parse ISO format timestamp
                    dt = datetime.fromisoformat(job.submitted_at.replace("Z", "+00:00"))
                    # Use negative timestamp for reverse chronological order (newest first)
                    time_priority = -dt.timestamp()
                else:
                    # Jobs without submitted_at go to the end
                    time_priority = float("inf")
            except Exception:
                # Invalid timestamps go to the end
                time_priority = float("inf")

            # Secondary sorting: user priority (root first), then user name, then status
            user_priority = (
                0 if job.datasite_owner_email == self.current_user_email else 1
            )
            status_priority = {"inbox": 1, "approved": 2, "done": 3}.get(job.status, 4)

            return (
                time_priority,
                user_priority,
                job.datasite_owner_email,
                status_priority,
                job.name.lower(),
            )

        sorted_jobs = sorted(current_jobs, key=job_sort_key)
        return JobsList(sorted_jobs, self.target_datasite_owner_email)


def get_client(
    syftbox_folder_path: str, email: str, user_email: Optional[str] = None
) -> JobClient:
    """
    Factory function to create a JobClient from SyftBox folder.

    Args:
        syftbox_folder_path: Path to the SyftBox folder
        email: Root user email address (explicit, no inference from folder name)
        user_email: Optional target user email for job views (defaults to root email)

    Returns:
        Configured JobClient instance
    """
    config = SyftJobConfig.from_syftbox_folder(syftbox_folder_path, email)
    return JobClient(config, user_email)
