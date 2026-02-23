"""Unit tests for version negotiation feature."""

import pytest
from syft_client.sync.syftbox_manager import SyftboxManager
from syft_client.sync.version.version_info import VersionInfo
from syft_client.sync.version.exceptions import (
    VersionUnknownError,
)


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
        assert (
            restored.min_supported_syft_client_version
            == original.min_supported_syft_client_version
        )
        assert (
            restored.min_supported_protocol_version
            == original.min_supported_protocol_version
        )

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
        ds_manager, do_manager = (
            SyftboxManager.pair_with_mock_drive_service_connection()
        )

        # Version should be written during initialization - verify via public API
        # DS can read DO's version after peer setup (they're auto-added as peers)
        ds_version = do_manager.version_manager.load_peer_version(ds_manager.email)
        do_version = ds_manager.version_manager.load_peer_version(do_manager.email)

        assert ds_version is not None, "DS version should be readable by DO"
        assert do_version is not None, "DO version should be readable by DS"

    def test_version_shared_on_add_peer(self):
        """Test that version file is shared when adding a peer."""
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
            add_peers=False
        )

        # Before adding peer, DO cannot read DS's version
        ds_version_before = do_manager.version_manager.load_peer_version(
            ds_manager.email
        )
        assert ds_version_before is None, "DO should not be able to read DS version yet"

        # DS adds DO as peer
        ds_manager.add_peer(do_manager.email)

        # Now DO should be able to read DS's version (shared on add_peer)
        ds_version_after = do_manager.version_manager.load_peer_version(
            ds_manager.email
        )
        assert ds_version_after is not None, (
            "DO should be able to read DS version after add_peer"
        )

    def test_version_shared_on_approve_peer(self):
        """Test that version file is shared when approving a peer request."""
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
            add_peers=False
        )

        # DS adds DO as peer (creates pending request)
        ds_manager.add_peer(do_manager.email)
        do_manager.load_peers()

        # Before approval, DS cannot read DO's version
        do_version_before = ds_manager.version_manager.load_peer_version(
            do_manager.email
        )
        assert do_version_before is None, (
            "DS should not be able to read DO version before approval"
        )

        # DO approves DS
        do_manager.approve_peer_request(ds_manager.email)

        # Now DS should be able to read DO's version (shared on approve)
        do_version_after = ds_manager.version_manager.load_peer_version(
            do_manager.email
        )
        assert do_version_after is not None, (
            "DS should be able to read DO version after approval"
        )

    def test_load_peer_version(self):
        """Test that peer version can be loaded."""
        ds_manager, do_manager = (
            SyftboxManager.pair_with_mock_drive_service_connection()
        )

        # DS should be able to load DO's version
        version = ds_manager.version_manager.load_peer_version(do_manager.email)
        assert version is not None
        assert version.syft_client_version == VersionInfo.current().syft_client_version

    def test_load_peer_version_without_permission(self):
        """Test that peer version returns None without permission."""
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
            add_peers=False
        )

        # DS tries to load DO's version without having permission
        version = ds_manager.version_manager.load_peer_version(do_manager.email)
        assert version is None

    def test_load_peer_versions_parallel(self):
        """Test that multiple peer versions can be loaded in parallel."""
        from syft_client.sync.connections.drive.mock_drive_service import (
            MockDriveFile,
            MockPermission,
        )
        from syft_client.sync.connections.drive.gdrive_transport import (
            SYFT_VERSION_FILE,
        )

        ds_manager, do_manager = (
            SyftboxManager.pair_with_mock_drive_service_connection()
        )

        # Get the backing store to manually insert a version file for a third peer
        backing_store = ds_manager._connection_router.connections[
            0
        ].drive_service._backing_store

        # Create a version file for a third peer manually in the backing store
        third_peer_email = "third_peer@test.com"
        third_peer_version = VersionInfo.current()
        version_file = MockDriveFile(
            name=SYFT_VERSION_FILE,
            mimeType="application/json",
            parents=[],  # Root level, owned by third peer
            owners=[{"emailAddress": third_peer_email}],
            content=third_peer_version.to_json(),
        )
        backing_store.add_file(version_file)

        # Share the version file with DS (add read permission)
        backing_store.add_permission(
            version_file.id,
            MockPermission(
                type="user",
                role="reader",
                emailAddress=ds_manager.email,
            ),
        )

        # Load peer versions for both DO and the third peer in parallel
        peer_emails = [do_manager.email, third_peer_email]
        versions = ds_manager.version_manager.load_peer_versions_parallel(
            peer_emails, force=True
        )

        assert len(versions) == 2
        assert versions[do_manager.email] is not None
        assert versions[third_peer_email] is not None
        assert (
            versions[third_peer_email].syft_client_version
            == third_peer_version.syft_client_version
        )


class TestForceSubmission:
    """Tests for force_submission parameter."""

    def test_job_submission_blocked_without_version(self):
        """Test that job submission is blocked when peer version is unknown."""
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
            add_peers=False,
            sync_automatically=False,
            check_versions=True,
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
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
            add_peers=False,
            sync_automatically=False,
            check_versions=True,
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

        job_dir = (
            ds_manager.syftbox_folder
            / do_manager.email
            / "app_data"
            / "job"
            / "test.force.job"
        )
        assert job_dir.exists(), "Job directory should exist after force submission"


class TestIgnoreVersionFlags:
    """Tests for ignore_protocol_version and ignore_client_version flags."""

    def test_ignore_client_version(self):
        """Test that ignore_client_version bypasses client version check."""
        ds_manager, do_manager = (
            SyftboxManager.pair_with_mock_drive_service_connection()
        )

        # Write an incompatible client version for DO using public API
        current = VersionInfo.current()
        different_version = VersionInfo(
            syft_client_version="0.0.1",  # Different
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        do_manager._connection_router.write_version_file(different_version)

        # Clear DS's cached version of DO and reload
        ds_manager.version_manager.clear_peer_version(do_manager.email)
        ds_manager.version_manager.load_peer_version(do_manager.email)

        # Without ignore flag, should be incompatible
        ds_manager.version_manager.ignore_client_version = False
        assert not ds_manager.version_manager.is_peer_version_compatible(
            do_manager.email
        )

        # With ignore flag, should be compatible
        ds_manager.version_manager.ignore_client_version = True
        assert ds_manager.version_manager.is_peer_version_compatible(do_manager.email)

    def test_ignore_protocol_version(self):
        """Test that ignore_protocol_version bypasses protocol version check."""
        ds_manager, do_manager = (
            SyftboxManager.pair_with_mock_drive_service_connection()
        )

        # Write an incompatible protocol version for DO using public API
        current = VersionInfo.current()
        different_version = VersionInfo(
            syft_client_version=current.syft_client_version,
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version="0.0.1",  # Different
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        do_manager._connection_router.write_version_file(different_version)

        # Clear DS's cached version of DO and reload
        ds_manager.version_manager.clear_peer_version(do_manager.email)
        ds_manager.version_manager.load_peer_version(do_manager.email)

        # Without ignore flag, should be incompatible
        ds_manager.version_manager.ignore_protocol_version = False
        assert (
            ds_manager.version_manager.is_peer_version_compatible(do_manager.email)
            is False
        )

        # With ignore flag, should be compatible
        ds_manager.version_manager.ignore_protocol_version = True
        assert (
            ds_manager.version_manager.is_peer_version_compatible(do_manager.email)
            is True
        )

    def test_ignore_both_versions(self):
        """Test that ignoring both versions makes any peer compatible."""
        ds_manager, do_manager = (
            SyftboxManager.pair_with_mock_drive_service_connection()
        )

        # Write completely different versions for DO using public API
        current = VersionInfo.current()
        different_version = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version="0.0.1",
            protocol_version="0.0.1",
            min_supported_protocol_version="0.0.1",
            updated_at=current.updated_at,
        )
        do_manager._connection_router.write_version_file(different_version)

        # Clear DS's cached version and reload
        ds_manager.version_manager.clear_peer_version(do_manager.email)
        ds_manager.version_manager.ignore_client_version = True
        ds_manager.version_manager.ignore_protocol_version = True
        ds_manager.version_manager.load_peer_version(do_manager.email)

        assert (
            ds_manager.version_manager.is_peer_version_compatible(do_manager.email)
            is True
        )


class TestVersionMismatchBehavior:
    """Tests for version mismatch behavior during operations."""

    def test_sync_skips_incompatible_peers(self):
        """Test that sync skips peers with incompatible versions (DO side)."""
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
            check_versions=True,
        )

        # Write an incompatible version for DS using public API
        current = VersionInfo.current()
        incompatible = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        ds_manager._connection_router.write_version_file(incompatible)

        # Clear cached version so it sees the incompatible version
        do_manager.version_manager.clear_peer_version(ds_manager.email)
        do_manager.version_manager.load_peer_version(ds_manager.email)

        # DO loads peers and syncs - should skip DS due to version mismatch
        do_manager.load_peers()
        do_manager.version_manager.suppress_version_warnings = True

        compatible_peers = do_manager.version_manager.get_compatible_peer_emails(
            [ds_manager.email], warn_incompatible=False
        )

        assert ds_manager.email not in compatible_peers

    @pytest.mark.skip(
        reason="skip_job_names parameter not in installed syft-job package"
    )
    def test_job_execution_skipped_with_incompatible_version(self):
        """Test that job execution is skipped (with warning) when submitter version is incompatible."""
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
            sync_automatically=False,
            use_in_memory_cache=False,
            check_versions=True,
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

        # Now change DS version to be incompatible using public API
        current = VersionInfo.current()
        incompatible = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        ds_manager._connection_router.write_version_file(incompatible)

        # Clear cached version so it sees the incompatible version
        do_manager.version_manager.clear_peer_version(ds_manager.email)
        do_manager.version_manager.load_peer_version(ds_manager.email)

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
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
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

        # Now change DS version to be incompatible using public API
        current = VersionInfo.current()
        incompatible = VersionInfo(
            syft_client_version="0.0.1",
            min_supported_syft_client_version=current.min_supported_syft_client_version,
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )
        ds_manager._connection_router.write_version_file(incompatible)

        # Clear cached version so it sees the incompatible version
        do_manager.version_manager.clear_peer_version(ds_manager.email)
        do_manager.version_manager.load_peer_version(ds_manager.email)

        # Mock the job_runner to avoid actual execution
        executed_jobs = []

        def mock_process_approved_jobs(
            stream_output=True, timeout=None, skip_job_names=None
        ):
            # Track that we were called without skip_job_names (force mode)
            executed_jobs.append(skip_job_names)

        do_manager.job_runner.process_approved_jobs = mock_process_approved_jobs

        # With force_execution=True, job_runner should be called without skip list
        do_manager.process_approved_jobs(force_execution=True)

        # Verify job_runner was called with no jobs to skip
        assert len(executed_jobs) == 1
        assert executed_jobs[0] is None  # No jobs skipped when force=True

    def test_version_upgrade_breaks_communication(self):
        """Test that version upgrade makes peers incompatible.

        Unit test equivalent of integration test_version_upgrade_breaks_communication.

        1. Initialize peers with matching versions and verify they are compatible
        2. Update one peer's version (simulating an upgrade)
        3. Reload the version and verify peers are now incompatible
        """
        # Phase 1: Create managers with compatible versions
        ds_manager, do_manager = SyftboxManager.pair_with_mock_drive_service_connection(
            check_versions=True,
        )

        # Verify initial version compatibility
        ds_manager.version_manager.load_peer_version(do_manager.email)
        do_manager.version_manager.load_peer_version(ds_manager.email)

        assert ds_manager.version_manager.is_peer_version_compatible(
            do_manager.email
        ), "DS should see DO as compatible initially"
        assert do_manager.version_manager.is_peer_version_compatible(
            ds_manager.email
        ), "DO should see DS as compatible initially"

        # Phase 2: Simulate DS "upgrading" to a new incompatible version
        current = VersionInfo.current()
        new_version = VersionInfo(
            syft_client_version="99.0.0",  # Incompatible version
            min_supported_syft_client_version="99.0.0",
            protocol_version=current.protocol_version,
            min_supported_protocol_version=current.min_supported_protocol_version,
            updated_at=current.updated_at,
        )

        # Write the new version using public API (simulating DS upgrading their client)
        ds_manager._connection_router.write_version_file(new_version)

        # Phase 3: Clear DO's cached version of DS and reload
        do_manager.version_manager.clear_peer_version(ds_manager.email)

        # Reload DS's version
        reloaded_version = do_manager.version_manager.load_peer_version(
            ds_manager.email
        )

        # Verify the new version was loaded
        assert reloaded_version is not None, "Should be able to reload peer version"
        assert reloaded_version.syft_client_version == "99.0.0", (
            "Reloaded version should be the upgraded version"
        )

        # Verify versions are now incompatible
        assert not do_manager.version_manager.is_peer_version_compatible(
            ds_manager.email
        ), "DO should now see DS as incompatible after version upgrade"
