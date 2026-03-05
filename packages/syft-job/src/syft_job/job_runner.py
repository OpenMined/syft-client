import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import List, Set

from . import __version__
from .config import SyftJobConfig

# Default timeout for job execution (5 minutes)
DEFAULT_JOB_TIMEOUT_SECONDS = 300


def get_job_timeout_seconds() -> int:
    """Get job timeout from environment variable or use default.

    Can be overridden by setting SYFT_DEFAULT_JOB_TIMEOUT_SECONDS environment variable.
    """
    return int(
        os.environ.get("SYFT_DEFAULT_JOB_TIMEOUT_SECONDS", DEFAULT_JOB_TIMEOUT_SECONDS)
    )


IS_IN_JOB_ENV_VAR = "SYFT_IS_IN_JOB"


class SyftJobRunner:
    """Job runner that monitors inbox folder for new jobs."""

    def __init__(self, config: SyftJobConfig, poll_interval: int = 5):
        """
        Initialize the job runner.

        Args:
            config: SyftJobConfig instance
            poll_interval: How often to check for new jobs (in seconds)
        """
        self.config = config
        self.poll_interval = poll_interval
        self.known_jobs: Set[str] = set()

        # Ensure directory structure exists for the root user
        self._ensure_root_user_directories()

    @classmethod
    def from_config(cls, config: SyftJobConfig) -> "SyftJobRunner":
        return cls(config)

    def _ensure_root_user_directories(self) -> None:
        """Ensure job directory structure exists for the root user."""
        root_email = self.config.email
        job_dir = self.config.get_job_dir(root_email)

        # Create job directory if it doesn't exist
        job_dir.mkdir(parents=True, exist_ok=True)
        print(f"Ensured directory exists: {job_dir}")

    def _get_jobs_in_inbox(self) -> List[str]:
        """Get list of job paths (ds_email/job_name) currently in inbox status."""
        job_dir = self.config.get_job_dir(self.config.email)

        if not job_dir.exists():
            return []

        jobs = []
        for ds_dir in job_dir.iterdir():
            if not ds_dir.is_dir():
                continue
            for item in ds_dir.iterdir():
                if item.is_dir() and (item / "config.yaml").exists():
                    if (
                        not (item / "approved").exists()
                        and not (item / "done").exists()
                    ):
                        jobs.append(f"{ds_dir.name}/{item.name}")

        return jobs

    def _print_new_job(self, job_name: str) -> None:
        """Print information about a new job in the inbox."""
        job_dir = self.config.get_job_dir(self.config.email) / job_name

        print(f"\n🔔 NEW JOB DETECTED: {job_name}")
        print(f"📁 Location: {job_dir}")

        # Check if run.sh exists and show first few lines
        run_script = job_dir / "run.sh"
        if run_script.exists():
            try:
                with open(run_script, "r") as f:
                    all_lines = f.readlines()
                lines = all_lines[:5]  # Show first 5 lines
                print("📝 Script preview:")
                for i, line in enumerate(lines, 1):
                    print(f"   {i}: {line.rstrip()}")
                if len(all_lines) > 5:
                    print("   ... (more lines)")
            except Exception as e:
                print(f"   Could not read script: {e}")

        # Check if config.yaml exists and show contents
        config_file = job_dir / "config.yaml"
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    content = f.read()
                print("⚙️  Config:")
                for line in content.split("\n"):
                    if line.strip():
                        print(f"   {line}")
            except Exception as e:
                print(f"   Could not read config: {e}")

        print("-" * 50)

    def reset_all_jobs(self) -> None:
        """
        Delete all jobs and recreate the job folder structure.

        This will:
        1. Delete all jobs in inbox, approved, and done folders
        2. Recreate the empty folder structure
        3. Reset the known jobs tracking
        """
        root_email = self.config.email
        job_dir = self.config.get_job_dir(root_email)

        print(f"🔄 RESETTING ALL JOBS for {root_email}")
        print(f"📁 Target directory: {job_dir}")

        if not job_dir.exists():
            print("📭 No job directory found - nothing to reset")
            self._ensure_root_user_directories()
            return

        # Count jobs before deletion
        total_jobs = 0
        job_counts = {}

        for status_dir in ["inbox", "approved", "done"]:
            status_path = job_dir / status_dir
            if status_path.exists():
                job_list = [item for item in status_path.iterdir() if item.is_dir()]
                job_counts[status_dir] = len(job_list)
                total_jobs += len(job_list)

                if job_list:
                    print(f"📋 Found {len(job_list)} jobs in {status_dir}:")
                    for job in job_list[:5]:  # Show first 5
                        print(f"   - {job.name}")
                    if len(job_list) > 5:
                        print(f"   ... and {len(job_list) - 5} more")

        if total_jobs == 0:
            print("📭 No jobs found to delete")
            self._ensure_root_user_directories()
            return

        # Confirm deletion
        print(f"\n⚠️  WARNING: This will permanently delete {total_jobs} jobs!")
        print("   This action cannot be undone.")

        try:
            # Delete the entire job directory
            print(f"🗑️  Deleting job directory: {job_dir}")
            shutil.rmtree(job_dir)

            # Recreate the folder structure
            print("📁 Recreating job folder structure...")
            self._ensure_root_user_directories()

            # Reset known jobs tracking
            self.known_jobs.clear()

            print("✅ Job reset completed successfully!")
            print("📊 Summary:")
            print(f"   - Deleted {total_jobs} jobs total")
            for status, count in job_counts.items():
                if count > 0:
                    print(f"   - {status}: {count} jobs deleted")
            print("   - Clean job directory recreated")

        except Exception as e:
            print(f"❌ Error during reset: {e}")
            print("🔧 Attempting to recreate job directory anyway...")
            try:
                self._ensure_root_user_directories()
                print("✅ Job directory recreated")
            except Exception as recovery_error:
                print(f"❌ Failed to recreate job directory: {recovery_error}")
                raise

    def check_for_new_jobs(self) -> None:
        """Check for new jobs in the inbox and print them."""
        current_jobs = set(self._get_jobs_in_inbox())
        new_jobs = current_jobs - self.known_jobs

        for job_name in new_jobs:
            self._print_new_job(job_name)

        # Update known jobs
        self.known_jobs = current_jobs

    def _get_jobs_in_approved(self) -> List[str]:
        """Get list of job paths (ds_email/job_name) currently in approved status."""
        job_dir = self.config.get_job_dir(self.config.email)

        if not job_dir.exists():
            return []

        jobs = []
        for ds_dir in job_dir.iterdir():
            if not ds_dir.is_dir():
                continue
            for item in ds_dir.iterdir():
                if item.is_dir() and (item / "config.yaml").exists():
                    if (item / "approved").exists() and not (item / "done").exists():
                        jobs.append(f"{ds_dir.name}/{item.name}")

        return jobs

    def _execute_job_streaming(
        self, job_name: str, timeout: int, user: str | None = None
    ) -> bool:
        """Execute job with real-time streaming output.

        Args:
            job_name: Name of the job to execute.
            timeout: Timeout in seconds.
            user: DS email who submitted the job. If None, searches.
        """
        job_dir = self._resolve_job_dir(job_name, user)
        run_script = job_dir / "run.sh"

        # Log prefix for streaming output
        log_prefix = f"[{self.config.email}][{job_name}]"

        # Make run.sh executable
        os.chmod(run_script, 0o755)

        # Prepare environment variables
        env = os.environ.copy()
        env["SYFTBOX_FOLDER"] = self.config.syftbox_folder_path_str
        env["SYFTBOX_EMAIL"] = self.config.email
        env[IS_IN_JOB_ENV_VAR] = "true"
        # Disable Python output buffering so streaming works in real-time
        env["PYTHONUNBUFFERED"] = "1"

        # Prepare log files for streaming output
        stdout_file = job_dir / "stdout.txt"
        stderr_file = job_dir / "stderr.txt"

        import selectors

        with (
            open(stdout_file, "w") as stdout_f,
            open(stderr_file, "w") as stderr_f,
        ):
            process = subprocess.Popen(
                ["bash", str(run_script)],
                cwd=job_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )

            sel = selectors.DefaultSelector()
            sel.register(process.stdout, selectors.EVENT_READ, data="stdout")
            sel.register(process.stderr, selectors.EVENT_READ, data="stderr")

            start_time = time.time()
            timed_out = False

            # Stream output while process is running
            while process.poll() is None:
                if time.time() - start_time > timeout:
                    process.kill()
                    process.wait()
                    timed_out = True
                    print(f"⏰ Job {job_name} timed out after {timeout // 60} minutes")
                    stdout_f.write("\n--- PROCESS TIMED OUT ---\n")
                    stderr_f.write("\n--- PROCESS TIMED OUT ---\n")
                    break

                for key, _ in sel.select(timeout=0.1):
                    line = key.fileobj.readline()
                    if line:
                        if key.data == "stdout":
                            print(f"{log_prefix} {line}", end="", flush=True)
                            stdout_f.write(line)
                        else:
                            print(f"{log_prefix} STDERR: {line}", end="", flush=True)
                            stderr_f.write(line)

            sel.close()

            # Process exited - drain any remaining data from pipes
            # Using read() gets everything: Python's buffer + OS pipe buffer
            remaining_stdout = process.stdout.read()
            remaining_stderr = process.stderr.read()

            if remaining_stdout:
                for line in remaining_stdout.splitlines(keepends=True):
                    print(f"{log_prefix} {line}", end="", flush=True)
                    stdout_f.write(line)

            if remaining_stderr:
                for line in remaining_stderr.splitlines(keepends=True):
                    print(f"{log_prefix} STDERR: {line}", end="", flush=True)
                    stderr_f.write(line)

            returncode = process.returncode if not timed_out else -1

        return returncode

    def _execute_job_captured(
        self, job_name: str, timeout: int, user: str | None = None
    ) -> int:
        """Execute job with captured output (non-streaming).

        Args:
            job_name: Name of the job to execute.
            timeout: Timeout in seconds.
            user: DS email who submitted the job. If None, searches.
        """
        job_dir = self._resolve_job_dir(job_name, user)
        run_script = job_dir / "run.sh"

        # Make run.sh executable
        os.chmod(run_script, 0o755)

        # Prepare environment variables
        env = os.environ.copy()
        env["SYFTBOX_FOLDER"] = self.config.syftbox_folder_path_str
        env["SYFTBOX_EMAIL"] = self.config.email
        env[IS_IN_JOB_ENV_VAR] = "true"
        # Disable Python output buffering for consistency
        env["PYTHONUNBUFFERED"] = "1"

        # Execute run.sh and capture output
        result = subprocess.run(
            ["bash", str(run_script)],
            cwd=job_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )

        # Write stdout to stdout.txt
        stdout_file = job_dir / "stdout.txt"
        with open(stdout_file, "w") as f:
            f.write(result.stdout)

        # Write stderr to stderr.txt
        stderr_file = job_dir / "stderr.txt"
        with open(stderr_file, "w") as f:
            f.write(result.stderr)

        return result.returncode

    def _execute_job(
        self,
        job_name: str,
        stream_output: bool = True,
        timeout: int | None = None,
        user: str | None = None,
    ) -> bool:
        """
        Execute run.sh for a job in the approved directory.

        Args:
            job_name: Name of the job to execute.
            stream_output: If True (default), stream output in real-time.
                        If False, capture output at end (CI-friendly).
            timeout: Timeout in seconds. Defaults to 300 (5 minutes).
                    Can also be set via SYFT_DEFAULT_JOB_TIMEOUT_SECONDS env var.
            user: DS email who submitted the job. If None, searches.

        Returns:
            bool: True if execution was successful, False otherwise
        """
        if timeout is None:
            timeout = get_job_timeout_seconds()
        job_dir = self._resolve_job_dir(job_name, user)
        run_script = job_dir / "run.sh"

        if not run_script.exists():
            print(f"❌ No run.sh found in {job_name}")
            return False

        self._prepare_outputs_dir(job_name, user)

        print(f"🚀 Executing job: {job_name}")
        print(f"📁 Job directory: {job_dir}")

        try:
            # Execute with streaming or captured output
            if stream_output:
                returncode = self._execute_job_streaming(job_name, timeout, user)
            else:
                returncode = self._execute_job_captured(job_name, timeout, user)

            # Create done marker file to mark job as completed
            (job_dir / "done").touch()

            # Write return code
            returncode_file = job_dir / "returncode.txt"
            with open(returncode_file, "w") as f:
                f.write(str(returncode))

            stdout_file = job_dir / "stdout.txt"
            stderr_file = job_dir / "stderr.txt"

            if returncode == 0:
                print(f"✅ Job {job_name} completed successfully")
                print(f"📄 Output written to {stdout_file}")
            else:
                print(f"⚠️  Job {job_name} completed with return code {returncode}")
                print(f"📄 Output written to {stdout_file}")
                try:
                    if stderr_file.exists() and stderr_file.stat().st_size > 0:
                        print(f"📄 Error output written to {stderr_file}")
                except OSError:
                    pass

            return True

        except subprocess.TimeoutExpired:
            print(f"⏰ Job {job_name} timed out after {timeout // 60} minutes")
            return False
        except Exception as e:
            print(f"❌ Error executing job {job_name}: {e}")
            return False

    def _prepare_outputs_dir(self, job_name: str, user: str | None = None) -> None:
        """Clear and recreate outputs dir with owner-only read permissions."""
        job_dir = self._resolve_job_dir(job_name, user)
        outputs_dir = job_dir / "outputs"
        if outputs_dir.exists():
            shutil.rmtree(outputs_dir)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        from syft_perm import SyftPermContext

        datasite = self.config.syftbox_folder / self.config.email
        rel_path = str(outputs_dir.relative_to(datasite)) + "/"
        ctx = SyftPermContext(datasite=datasite)
        folder = ctx.open(rel_path)
        folder.grant_read_access(self.config.email)

    def _resolve_job_dir(self, job_name: str, user: str | None = None) -> Path:
        """Resolve the job directory, searching if user is not specified."""
        base_job_dir = self.config.get_job_dir(self.config.email)
        if user:
            return base_job_dir / user / job_name
        # Search for the job across all user subdirectories
        matches = list(base_job_dir.glob(f"*/{job_name}"))
        if len(matches) == 1:
            return matches[0]
        if len(matches) == 0:
            raise FileNotFoundError(f"Job '{job_name}' not found under {base_job_dir}")
        raise ValueError(
            f"Multiple jobs named '{job_name}' found: {matches}. "
            "Pass user= to disambiguate."
        )

    def _get_job_submitter(self, job_name: str, user: str | None = None) -> str | None:
        """Read submitted_by from job config.yaml."""
        job_dir = self._resolve_job_dir(job_name, user)
        config_file = job_dir / "config.yaml"
        if not config_file.exists():
            return None
        try:
            import yaml

            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
            return config.get("submitted_by")
        except Exception:
            return None

    def _get_job_info(self, job_name: str, user: str | None = None):
        """Create a JobInfo for a job by name."""
        from .client import JobClient
        from .job import JobInfo

        job_dir = self._resolve_job_dir(job_name, user)
        client = JobClient(config=self.config)
        status = client.get_job_status(job_dir)
        import yaml

        config_file = job_dir / "config.yaml"
        with open(config_file, "r") as f:
            job_config = yaml.safe_load(f)
        return JobInfo(
            name=job_config.get("name", job_name),
            datasite_owner_email=self.config.email,
            status=status,
            submitted_by=job_config.get("submitted_by", "unknown"),
            location=job_dir,
            client=client,
            current_user_email=self.config.email,
        )

    def process_approved_jobs(
        self,
        stream_output: bool = True,
        timeout: int | None = None,
        skip_job_names: list[str] | None = None,
        share_outputs_with_submitter: bool = False,
        share_logs_with_submitter: bool = False,
    ) -> None:
        """Process all jobs in the approved directory.

        Args:
            stream_output: If True (default), stream output in real-time.
                        If False, capture output at end (CI-friendly).
            timeout: Timeout in seconds per job. Defaults to 300 (5 minutes).
                    Can also be set via SYFT_DEFAULT_JOB_TIMEOUT_SECONDS env var.
            skip_job_names: Optional list of job names to skip.
            share_outputs_with_submitter: If True, grant read access on outputs to submitter.
            share_logs_with_submitter: If True, grant read access on logs to submitter.
        """
        approved_jobs = self._get_jobs_in_approved()

        if not approved_jobs:
            return

        # Filter out jobs to skip
        if skip_job_names:
            skip_set = set(skip_job_names)
            approved_jobs = [j for j in approved_jobs if j not in skip_set]

        if not approved_jobs:
            return

        print(f"📋 Found {len(approved_jobs)} job(s) in approved directory")

        for job_path in approved_jobs:
            # job_path is "{ds_email}/{job_name}" from _get_jobs_in_approved
            user, job_name = job_path.split("/", 1)
            print(f"\n{'=' * 50}")
            self._execute_job(
                job_name, stream_output=stream_output, timeout=timeout, user=user
            )
            self.share_job_results(
                job_name,
                share_outputs_with_submitter,
                share_logs_with_submitter,
                user=user,
            )
            print(f"{'=' * 50}")

        if approved_jobs:
            print(f"\n✅ Processed {len(approved_jobs)} job(s)")

    def share_job_results(
        self,
        job_name: str,
        share_outputs: bool,
        share_logs: bool,
        user: str | None = None,
    ) -> None:
        """Share job outputs/logs with submitter if requested.

        Args:
            job_name: Name of the job (e.g. "my.job").
            share_outputs: Whether to share output files.
            share_logs: Whether to share log files.
            user: DS email who submitted the job. If None, searches all
                  user subdirectories and raises if ambiguous.
        """
        if not share_outputs and not share_logs:
            return
        submitter = self._get_job_submitter(job_name, user)
        if not submitter:
            return
        job_info = self._get_job_info(job_name, user)
        if share_outputs:
            job_info.share_outputs([submitter])
        if share_logs:
            job_info.share_logs([submitter])

    def run(self) -> None:
        """Start monitoring the inbox and approved folders for jobs."""
        root_email = self.config.email
        job_dir = self.config.get_job_dir(root_email)

        print(f"🚀 SyftJob Runner started: version: {__version__}")
        print(f"👤 Monitoring jobs for: {root_email}")
        print(f"📂 Job directory: {job_dir}")
        print(f"⏱️  Poll interval: {self.poll_interval} seconds")
        print("⏹️  Press Ctrl+C to stop")
        print("=" * 50)

        # Initialize known jobs with current state
        self.known_jobs = set(self._get_jobs_in_inbox())
        if self.known_jobs:
            print(
                f"📋 Found {len(self.known_jobs)} existing jobs: "
                f"{', '.join(self.known_jobs)}"
            )
        else:
            print("📭 No existing jobs found")
        print("-" * 50)

        try:
            while True:
                self.check_for_new_jobs()
                self.process_approved_jobs()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print("\n🛑 Job runner stopped by user")
        except Exception as e:
            print(f"\n❌ Job runner encountered an error: {e}")
            raise


def create_runner(
    syftbox_folder_path: str, email: str, poll_interval: int = 5
) -> SyftJobRunner:
    """
    Factory function to create a SyftJobRunner from SyftBox folder.

    Args:
        syftbox_folder_path: Path to the SyftBox folder
        email: Email address of the user (no inference, explicit required)
        poll_interval: How often to check for new jobs (in seconds)

    Returns:
        Configured SyftJobRunner instance
    """
    config = SyftJobConfig.from_syftbox_folder(syftbox_folder_path, email)
    return SyftJobRunner(config, poll_interval)
