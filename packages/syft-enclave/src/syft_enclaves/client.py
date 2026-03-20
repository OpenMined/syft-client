from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.peers.peer import Peer
from syft_client.sync.peers.peer_list import PeerList
from syft_datasets.dataset_manager import SyftDatasetManager
from syft_job.job import JobsList
from syft_job.models.config import JobSubmissionMetadata
from syft_job.models.state import JobState, JobStatus, PartyApprovalStatus
from syft_perms.syftperm_context import SyftPermContext

from syft_enclaves.enclave_job_client import EnclaveJobClient
from syft_enclaves.utils import (
    create_configs,
    create_managers,
    setup_callbacks,
    setup_connections,
    wire_peers,
    write_versions,
)


class SyftEnclaveClient:
    def __init__(self, manager: SyftboxManager):
        self._manager = manager

    @property
    def email(self) -> str:
        return self._manager.email

    @property
    def peers(self) -> PeerList:
        return self._manager.peers

    def add_peer(self, peer_email: str, force: bool = False, verbose: bool = True):
        self._manager.add_peer(peer_email, force=force, verbose=verbose)

    def load_peers(self):
        self._manager.load_peers()

    def approve_peer_request(
        self,
        email_or_peer: str | Peer,
        verbose: bool = True,
        peer_must_exist: bool = True,
    ):
        self._manager.approve_peer_request(
            email_or_peer, verbose=verbose, peer_must_exist=peer_must_exist
        )

    def reject_peer_request(self, email_or_peer: str | Peer):
        self._manager.reject_peer_request(email_or_peer)

    def sync(self):
        self._manager.sync()

    def create_dataset(self, *args, **kwargs):
        return self._manager.create_dataset(*args, **kwargs)

    def share_private_dataset(self, tag: str, enclave_email: str):
        self._manager.share_private_dataset(tag, enclave_email)

    @property
    def datasets(self) -> SyftDatasetManager:
        return self._manager.dataset_manager

    @property
    def jobs(self) -> JobsList:
        return self._manager.job_client.jobs

    def submit_python_job(
        self,
        enclave_email: str,
        code_path: str,
        job_name: Optional[str] = "",
        datasets: Optional[dict[str, list[str]]] = None,
        **kwargs,
    ):
        """Submit a Python job to an enclave, then push files via sync."""
        job_dir = self._manager.job_client.submit_python_job(
            enclave_email, code_path, job_name, datasets=datasets, **kwargs
        )
        self._manager.push_job_files(job_dir)

    def receive_jobs(self):
        """Receive and distribute enclave jobs to relevant DOs.

        1. Scans inbox for new submissions
        2. For enclave jobs (with datasets), forwards files to each DO
        3. Creates JobState with PartyApprovalStatus per DO
        4. Sets permissions and marks as distributed
        """
        self._manager.job_client.scan_inbox()
        inbox_dir = self._manager.job_client.config.get_all_submissions_dir(
            self._manager.email
        )
        if not inbox_dir.exists():
            return

        for ds_dir in inbox_dir.iterdir():
            if not ds_dir.is_dir():
                continue
            for job_dir in ds_dir.iterdir():
                if not job_dir.is_dir():
                    continue
                self._try_distribute_job(ds_dir.name, job_dir)

    def _try_distribute_job(self, ds_email: str, job_dir: Path):
        """Distribute a single enclave job to relevant DOs if not yet distributed."""
        config_path = job_dir / "config.yaml"
        if not config_path.exists():
            return

        config = JobSubmissionMetadata.load(config_path)
        if config.job_type != "enclave" or not config.datasets:
            return

        review_dir = self._manager.job_client.config.get_review_job_dir(
            self._manager.email, ds_email, job_dir.name
        )
        distributed_marker = review_dir / "distributed"
        if distributed_marker.exists():
            return

        do_emails = list(config.datasets.keys())
        self._forward_job_to_dos(job_dir, do_emails)
        self._save_enclave_job_state(review_dir, do_emails, config.datasets)
        self._set_job_permissions(job_dir, do_emails)

        distributed_marker.parent.mkdir(parents=True, exist_ok=True)
        distributed_marker.write_text("distributed")

    def _forward_job_to_dos(self, job_dir: Path, do_emails: list[str]):
        """Forward job files to DOs via the event-based outbox mechanism."""
        files = self._collect_job_files(job_dir)
        events_message = (
            self._manager.datasite_owner_syncer.event_cache.create_events_for_files(
                files
            )
        )
        self._manager.datasite_owner_syncer.queue_event_for_syftbox(
            recipients=do_emails,
            file_change_events_message=events_message,
        )
        self._manager.datasite_owner_syncer.process_syftbox_events_queue()

    def _collect_job_files(self, job_dir: Path) -> dict[Path, bytes]:
        """Read all files under job_dir, return {path_in_datasite: bytes}."""
        datasite_dir = self._manager.syftbox_folder / self._manager.email
        files = {}
        for f in job_dir.rglob("*"):
            if not f.is_file():
                continue
            path_in_datasite = f.relative_to(datasite_dir)
            files[Path(path_in_datasite)] = f.read_bytes()
        return files

    def _save_enclave_job_state(
        self,
        review_dir: Path,
        do_emails: list[str],
        datasets: dict[str, list[str]],
    ):
        """Create and save JobState with PartyApprovalStatus entries per DO."""
        approval_states = [
            PartyApprovalStatus(
                party=do_email,
                dataset=",".join(datasets.get(do_email, [])),
            )
            for do_email in do_emails
        ]
        state = JobState(
            status=JobStatus.PENDING,
            received_at=datetime.now(timezone.utc),
            approval_states=approval_states,
        )
        review_dir.mkdir(parents=True, exist_ok=True)
        state.save(review_dir / "state.yaml")

    def _set_job_permissions(self, job_dir: Path, do_emails: list[str]):
        """Grant DOs read access to job submission and review dirs."""
        datasite = self._manager.syftbox_folder / self._manager.email
        ctx = SyftPermContext(datasite=datasite)
        inbox_rel = job_dir.relative_to(datasite)
        for do_email in do_emails:
            ctx.open(inbox_rel).grant_read_access(do_email)

    @classmethod
    def quad_with_mock_drive_service_connection(
        cls,
        enclave_email: str | None = None,
        do1_email: str | None = None,
        do2_email: str | None = None,
        ds_email: str | None = None,
        use_in_memory_cache: bool = True,
    ) -> tuple[
        "SyftEnclaveClient",
        "SyftEnclaveClient",
        "SyftEnclaveClient",
        "SyftEnclaveClient",
    ]:
        """Create 4 interconnected clients for testing enclave scenarios.

        Peer topology:
        - Enclave: peers with DO1, DO2, DS
        - DO1: peers with DS, Enclave (not DO2)
        - DO2: peers with DS, Enclave (not DO1)
        - DS: peers with DO1, DO2, Enclave

        Returns:
            Tuple of (enclave, do1, do2, ds)
        """
        configs = create_configs(
            enclave_email, do1_email, do2_email, ds_email, use_in_memory_cache
        )
        managers = create_managers(configs)
        setup_connections(managers)
        setup_callbacks(managers)
        write_versions(managers)
        wire_peers(managers)

        for m in managers:
            m.job_client = EnclaveJobClient(m.job_client)

        return tuple(cls(m) for m in managers)
