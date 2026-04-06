"""Tests for Wave 4: sync service registration and CLI wiring."""

from syft_bg.services.manager import ServiceManager
from syft_bg.services.registry import SERVICES


class TestSyncServiceRegistry:
    def test_sync_in_registry(self):
        assert "sync" in SERVICES
        assert SERVICES["sync"].name == "sync"

    def test_sync_has_paths(self):
        svc = SERVICES["sync"]
        assert "sync" in str(svc.pid_file)
        assert "sync" in str(svc.log_file)


class TestServiceManagerOrdering:
    def test_start_all_starts_sync_first(self):
        manager = ServiceManager()
        started = []
        original_start = type(manager).start_service

        def track_start(self, name):
            started.append(name)
            return (True, f"{name} started")

        type(manager).start_service = track_start
        try:
            manager.start_all()
            assert started[0] == "sync"
            assert len(started) == len(manager.services)
        finally:
            type(manager).start_service = original_start

    def test_stop_all_stops_sync_last(self):
        manager = ServiceManager()
        stopped = []
        original_stop = type(manager).stop_service

        def track_stop(self, name):
            stopped.append(name)
            return (True, f"{name} stopped")

        type(manager).stop_service = track_stop
        try:
            manager.stop_all()
            assert stopped[-1] == "sync"
            assert len(stopped) == len(manager.services)
        finally:
            type(manager).stop_service = original_stop

    def test_restart_all_stops_consumers_first_then_starts_sync_first(self):
        manager = ServiceManager()
        calls = []
        original_start = type(manager).start_service
        original_stop = type(manager).stop_service

        def track_start(self, name):
            calls.append(("start", name))
            return (True, f"{name} started")

        def track_stop(self, name):
            calls.append(("stop", name))
            return (True, f"{name} stopped")

        type(manager).start_service = track_start
        type(manager).stop_service = track_stop
        try:
            manager.restart_all()
            stop_calls = [name for op, name in calls if op == "stop"]
            start_calls = [name for op, name in calls if op == "start"]
            # sync stopped last
            assert stop_calls[-1] == "sync"
            # sync started first
            assert start_calls[0] == "sync"
            # all stops happen before all starts
            last_stop_idx = max(i for i, (op, _) in enumerate(calls) if op == "stop")
            first_start_idx = min(i for i, (op, _) in enumerate(calls) if op == "start")
            assert last_stop_idx < first_start_idx
        finally:
            type(manager).start_service = original_start
            type(manager).stop_service = original_stop


class TestSyncServiceManagerIntegration:
    def test_sync_listed(self):
        manager = ServiceManager()
        assert "sync" in manager.list_services()

    def test_sync_service_accessible(self):
        manager = ServiceManager()
        svc = manager.get_service("sync")
        assert svc is not None
        assert svc.name == "sync"
