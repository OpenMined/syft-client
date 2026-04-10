"""Tests for sync service registration and CLI wiring."""

from syft_bg.services.manager import ServiceManager
from syft_bg.services.registry import SERVICE_REGISTRY


class TestSyncServiceRegistry:
    def test_sync_in_registry(self):
        assert "sync" in SERVICE_REGISTRY
        assert SERVICE_REGISTRY["sync"].name == "sync"

    def test_sync_has_paths(self):
        svc = SERVICE_REGISTRY["sync"]
        assert "sync" in str(svc.pid_file)
        assert "sync" in str(svc.log_file)


class TestSyncServiceManagerIntegration:
    def test_sync_listed(self):
        manager = ServiceManager()
        assert "sync" in manager.list_services()

    def test_sync_service_accessible(self):
        manager = ServiceManager()
        svc = manager.get_service("sync")
        assert svc is not None
        assert svc.name == "sync"
