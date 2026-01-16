"""Unit tests for version negotiation feature."""

import pytest
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.version.version_info import VersionInfo
from syft_client.sync.version.exceptions import (
    VersionMismatchError,
    VersionUnknownError,
)
from tests.unit.utils import setup_mock_peer_version


class TestVersionInfo:
    """Tests for VersionInfo model."""

    def test_current_version_creates_valid_info(self):
        """Test that VersionInfo.current() creates valid version info."""
        version_info = VersionInfo.current()
        assert version_info.syft_client_version is not None
        assert version_info.protocol_version is not None
        assert version_info.min_supported_syft_client_version is not None
        assert version_info.min_supported_protocol_version is not None
        assert version_info.updated_at is not None

    def test_version_info_json_roundtrip(self):
        """Test that VersionInfo can be serialized and deserialized."""
        original = VersionInfo.current()
        json_str = original.to_json()
        restored = VersionInfo.from_json(json_str)

        assert restored.syft_client_version == original.syft_client_version
        assert restored.protocol_version == original.protocol_version
        assert restored.min_supported_syft_client_version == original.min_supported_syft_client_version
        assert restored.min_supported_protocol_version == original.min_supported_protocol_version

    def test_compatible_versions_match(self):
        """Test that identical versions are compatible."""
        v1 = VersionInfo.current()
        v2 = VersionInfo.current()

        assert v1.is_compatible_with(v2) is True
        assert v2.is_compatible_with(v1) is True

    def test_incompatible_client_version(self):
        """Test that different client versions are incompatible."""
        v1 = VersionInfo.current()
        v2 = VersionInfo(
            syft_client_version="0.0.1",  # Different version
            min_supported_syft_client_version=v1.min_supported_syft_client_version,
            protocol_version=v1.protocol_version,
            min_supported_protocol_version=v1.min_supported_protocol_version,
            updated_at=v1.updated_at,
        )

        assert v1.is_compatible_with(v2, check_client=True) is False
        assert v1.is_compatible_with(v2, check_client=False) is True

    def test_incompatible_protocol_version(self):
        """Test that different protocol versions are incompatible."""
        v1 = VersionInfo.current()
        v2 = VersionInfo(
            syft_client_version=v1.syft_client_version,
            min_supported_syft_client_version=v1.min_supported_syft_client_version,
            protocol_version="0.0.1",  # Different version
            min_supported_protocol_version=v1.min_supported_protocol_version,
            updated_at=v1.updated_at,
        )

        assert v1.is_compatible_with(v2, check_protocol=True) is False
        assert v1.is_compatible_with(v2, check_protocol=False) is True

    def test_get_incompatibility_reason_client(self):
        """Test that incompatibility reason is returned for client version mismatch."""
        v1 = VersionInfo.current()
        v2 = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version=v1.min_supported_syft_client_version,
            protocol_version=v1.protocol_version,
            min_supported_protocol_version=v1.min_supported_protocol_version,
            updated_at=v1.updated_at,
        )

        reason = v1.get_incompatibility_reason(v2, check_client=True)
        assert reason is not None
        assert "client" in reason.lower()

    def test_get_incompatibility_reason_protocol(self):
        """Test that incompatibility reason is returned for protocol version mismatch."""
        v1 = VersionInfo.current()
        v2 = VersionInfo(
            syft_client_version=v1.syft_client_version,
            min_supported_syft_client_version=v1.min_supported_syft_client_version,
            protocol_version="0.0.1",
            min_supported_protocol_version=v1.min_supported_protocol_version,
            updated_at=v1.updated_at,
        )

        reason = v1.get_incompatibility_reason(v2, check_protocol=True)
        assert reason is not None
        assert "protocol" in reason.lower()


class TestVersionManager:
    """Tests for VersionManager."""

    def test_version_manager_writes_own_version(self):
        """Test that VersionManager writes version file on initialization."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Version should be written during initialization
        store = ds_manager.connection_router.connections[0].backing_store
        assert ds_manager.email in store.version_files
        assert do_manager.email in store.version_files

    def test_version_shared_on_add_peer(self):
        """Test that version file is shared when adding a peer."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
            add_peers=False
        )

        store = ds_manager.connection_router.connections[0].backing_store

        # Before adding peer, DS version is not shared with DO
        ds_permissions = store.version_file_permissions.get(ds_manager.email, [])
        assert do_manager.email not in ds_permissions

        # DS adds DO as peer
        ds_manager.add_peer(do_manager.email)

        # Now DS version should be shared with DO
        ds_permissions = store.version_file_permissions.get(ds_manager.email, [])
        assert do_manager.email in ds_permissions

    def test_version_shared_on_approve_peer(self):
        """Test that version file is shared when approving a peer request."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
            add_peers=False
        )

        store = ds_manager.connection_router.connections[0].backing_store

        # DS adds DO as peer (creates pending request)
        ds_manager.add_peer(do_manager.email)
        do_manager.load_peers()

        # Before approval, DO version is not shared with DS
        do_permissions = store.version_file_permissions.get(do_manager.email, [])
        assert ds_manager.email not in do_permissions

        # DO approves DS
        do_manager.approve_peer_request(ds_manager.email)

        # Now DO version should be shared with DS
        do_permissions = store.version_file_permissions.get(do_manager.email, [])
        assert ds_manager.email in do_permissions

    def test_load_peer_version(self):
        """Test that peer version can be loaded."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # DS should be able to load DO's version
        version = ds_manager._version_manager.load_peer_version(do_manager.email)
        assert version is not None
        assert version.syft_client_version == VersionInfo.current().syft_client_version

    def test_load_peer_version_without_permission(self):
        """Test that peer version returns None without permission."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
            add_peers=False
        )

        # DS tries to load DO's version without having permission
        version = ds_manager._version_manager.load_peer_version(do_manager.email)
        assert version is None

    def test_load_peer_versions_parallel(self):
        """Test that multiple peer versions can be loaded in parallel."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        store = ds_manager.connection_router.connections[0].backing_store

        # Create additional mock peers with version files
        setup_mock_peer_version(store, "peer1@test.com", ds_manager.email)
        setup_mock_peer_version(store, "peer2@test.com", ds_manager.email)

        peer_emails = ["peer1@test.com", "peer2@test.com", do_manager.email]
        versions = ds_manager._version_manager.load_peer_versions_parallel(peer_emails)

        assert len(versions) == 3
        assert all(v is not None for v in versions.values())


class TestForceSubmission:
    """Tests for force_submission parameter."""

    def test_job_submission_blocked_without_version(self):
        """Test that job submission is blocked when peer version is unknown."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
            add_peers=False,
            sync_automatically=False,
        )

        # DS adds DO but DO hasn't shared version with DS yet
        ds_manager.add_peer(do_manager.email)

        test_py_path = "/tmp/test_version.py"
        with open(test_py_path, "w") as f:
            f.write('print("hello")')

        # Should raise because DO version is unknown to DS
        with pytest.raises(VersionUnknownError):
            ds_manager.submit_python_job(
                user=do_manager.email,
                code_path=test_py_path,
                job_name="test.job",
            )

    def test_job_submission_allowed_with_force(self):
        """Test that job submission works with force_submission=True when version is unknown."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
            add_peers=False,
            sync_automatically=False,
        )

        # DS adds DO as peer but DO hasn't approved yet
        # (so DO's version file isn't shared with DS)
        ds_manager.add_peer(do_manager.email)

        test_py_path = "/tmp/test_version_force.py"
        with open(test_py_path, "w") as f:
            f.write('print("hello")')

        # Without force, should fail because version is unknown
        with pytest.raises(VersionUnknownError):
            ds_manager.submit_python_job(
                user=do_manager.email,
                code_path=test_py_path,
                job_name="test.fail.job",
            )

        # Should work with force_submission=True (doesn't check version)
        # Note: job won't sync to DO since peer not approved, but submission succeeds
        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=test_py_path,
            job_name="test.force.job",
            force_submission=True,
        )
        # Verify job files were created (submission succeeded)
        import os
        job_dir = ds_manager.syftbox_folder / do_manager.email / "app_data" / "job" / "test.force.job"
        assert job_dir.exists(), "Job directory should exist after force submission"


class TestIgnoreVersionFlags:
    """Tests for ignore_protocol_version and ignore_client_version flags."""

    def test_ignore_client_version(self):
        """Test that ignore_client_version bypasses client version check."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Manually set a different client version in the backing store
        store = ds_manager.connection_router.connections[0].backing_store
        current = VersionInfo.current()
        different_version = VersionInfo(
            syft_client_version="0.0.1",  # Different
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        store.version_files[do_manager.email] = different_version.to_json()

        # Without ignore flag, should be incompatible
        ds_manager._version_manager.ignore_client_version = False
        ds_manager._version_manager.load_peer_version(do_manager.email)
        assert ds_manager._version_manager.is_peer_version_compatible(do_manager.email) is False

        # With ignore flag, should be compatible
        ds_manager._version_manager.ignore_client_version = True
        assert ds_manager._version_manager.is_peer_version_compatible(do_manager.email) is True

    def test_ignore_protocol_version(self):
        """Test that ignore_protocol_version bypasses protocol version check."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Manually set a different protocol version in the backing store
        store = ds_manager.connection_router.connections[0].backing_store
        current = VersionInfo.current()
        different_version = VersionInfo(
            syft_client_version=current.syft_client_version,
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version="0.0.1",  # Different
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        store.version_files[do_manager.email] = different_version.to_json()

        # Without ignore flag, should be incompatible
        ds_manager._version_manager.ignore_protocol_version = False
        ds_manager._version_manager.load_peer_version(do_manager.email)
        assert ds_manager._version_manager.is_peer_version_compatible(do_manager.email) is False

        # With ignore flag, should be compatible
        ds_manager._version_manager.ignore_protocol_version = True
        assert ds_manager._version_manager.is_peer_version_compatible(do_manager.email) is True

    def test_ignore_both_versions(self):
        """Test that ignoring both versions makes any peer compatible."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Manually set completely different versions
        store = ds_manager.connection_router.connections[0].backing_store
        current = VersionInfo.current()
        different_version = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version="0.0.1",
            protocol_version="0.0.1",
            min_supported_protocol_version="0.0.1",
            updated_at=current.updated_at,
        )
        store.version_files[do_manager.email] = different_version.to_json()

        ds_manager._version_manager.ignore_client_version = True
        ds_manager._version_manager.ignore_protocol_version = True
        ds_manager._version_manager.load_peer_version(do_manager.email)

        assert ds_manager._version_manager.is_peer_version_compatible(do_manager.email) is True


class TestVersionMismatchBehavior:
    """Tests for version mismatch behavior during operations."""

    def test_sync_skips_incompatible_peers(self):
        """Test that sync skips peers with incompatible versions (DO side)."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection()

        # Set incompatible version for DS
        store = ds_manager.connection_router.connections[0].backing_store
        current = VersionInfo.current()
        incompatible = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        store.version_files[ds_manager.email] = incompatible.to_json()

        # Clear cached version so it sees the incompatible version
        do_manager._version_manager._peer_versions.pop(ds_manager.email, None)
        do_manager._version_manager.load_peer_version(ds_manager.email)

        # DO loads peers and syncs - should skip DS due to version mismatch
        do_manager.load_peers()
        do_manager._version_manager.suppress_version_warnings = True

        compatible_peers = do_manager._version_manager.get_compatible_peer_emails(
            [ds_manager.email], warn_incompatible=False
        )

        assert ds_manager.email not in compatible_peers

    def test_job_execution_skipped_with_incompatible_version(self):
        """Test that job execution is skipped (with warning) when submitter version is incompatible."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
            sync_automatically=False,
            use_in_memory_cache=False,
        )

        # Submit a job first (with compatible versions)
        test_py_path = "/tmp/test_exec.py"
        with open(test_py_path, "w") as f:
            f.write('print("hello")')

        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=test_py_path,
            job_name="test.exec.job",
        )

        do_manager.sync()
        assert len(do_manager.job_client.jobs) == 1
        job = do_manager.job_client.jobs[0]
        job.approve()

        # Now change DS version to be incompatible
        store = ds_manager.connection_router.connections[0].backing_store
        current = VersionInfo.current()
        incompatible = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        store.version_files[ds_manager.email] = incompatible.to_json()

        # Clear cached version so it sees the incompatible version
        do_manager._version_manager._peer_versions.pop(ds_manager.email, None)
        do_manager._version_manager.load_peer_version(ds_manager.email)

        # Job execution should be skipped (with warning) due to version mismatch
        # Job remains approved but is not executed
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            do_manager.process_approved_jobs()
            # Check that a warning was issued about skipping the job
            assert len(w) >= 1
            assert any("Skipping job" in str(warning.message) for warning in w)

        # Job should still be approved (not executed, not rejected)
        assert job.status == "approved"

    def test_job_execution_forced_with_incompatible_version(self):
        """Test that job execution can be forced even when submitter version is incompatible."""
        ds_manager, do_manager = SyftboxManager.pair_with_in_memory_connection(
            sync_automatically=False,
            use_in_memory_cache=False,
        )

        # Submit a job first (with compatible versions)
        test_py_path = "/tmp/test_exec_force.py"
        with open(test_py_path, "w") as f:
            f.write('print("hello")')

        ds_manager.submit_python_job(
            user=do_manager.email,
            code_path=test_py_path,
            job_name="test.exec.force.job",
        )

        do_manager.sync()
        assert len(do_manager.job_client.jobs) == 1
        job = do_manager.job_client.jobs[0]
        job.approve()

        # Now change DS version to be incompatible
        store = ds_manager.connection_router.connections[0].backing_store
        current = VersionInfo.current()
        incompatible = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        store.version_files[ds_manager.email] = incompatible.to_json()

        # Clear cached version so it sees the incompatible version
        do_manager._version_manager._peer_versions.pop(ds_manager.email, None)
        do_manager._version_manager.load_peer_version(ds_manager.email)

        # Mock the job_runner to avoid actual execution
        executed_jobs = []
        original_process = do_manager.job_runner.process_approved_jobs

        def mock_process_approved_jobs(stream_output=True, timeout=None, skip_job_names=None):
            # Track that we were called without skip_job_names (force mode)
            executed_jobs.append(skip_job_names)

        do_manager.job_runner.process_approved_jobs = mock_process_approved_jobs

        # With force_execution=True, job_runner should be called without skip list
        do_manager.process_approved_jobs(force_execution=True)

        # Verify job_runner was called with no jobs to skip
        assert len(executed_jobs) == 1
        assert executed_jobs[0] is None  # No jobs skipped when force=True
