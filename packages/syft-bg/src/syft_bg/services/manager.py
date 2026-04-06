from typing import Optional

from syft_bg.services.base import Service, ServiceInfo, ServiceStatus
from syft_bg.services.registry import SERVICES


class ServiceManager:
    def __init__(self):
        self.services = SERVICES

    def list_services(self) -> list[str]:
        return list(self.services.keys())

    def get_service(self, name: str) -> Optional[Service]:
        return self.services.get(name)

    def get_all_status(self) -> dict[str, ServiceInfo]:
        return {name: svc.get_status() for name, svc in self.services.items()}

    def start_service(self, name: str) -> tuple[bool, str]:
        service = self.get_service(name)
        if not service:
            return (False, f"Unknown service: {name}")
        return service.start()

    def stop_service(self, name: str) -> tuple[bool, str]:
        service = self.get_service(name)
        if not service:
            return (False, f"Unknown service: {name}")
        return service.stop()

    def restart_service(self, name: str) -> tuple[bool, str]:
        service = self.get_service(name)
        if not service:
            return (False, f"Unknown service: {name}")
        return service.restart()

    def start_all(self) -> dict[str, tuple[bool, str]]:
        results = {}
        # Start sync first so consumers have a snapshot to read
        if "sync" in self.services:
            results["sync"] = self.start_service("sync")
        for name in self.services:
            if name not in results:
                results[name] = self.start_service(name)
        return results

    def stop_all(self) -> dict[str, tuple[bool, str]]:
        results = {}
        # Stop consumers first, then sync
        for name in self.services:
            if name != "sync":
                results[name] = self.stop_service(name)
        if "sync" in self.services:
            results["sync"] = self.stop_service("sync")
        return results

    def restart_all(self) -> dict[str, tuple[bool, str]]:
        stop_results = self.stop_all()
        start_results = self.start_all()
        return {
            name: start_results.get(name, stop_results.get(name, (False, "unknown")))
            for name in self.services
        }

    def get_logs(self, name: str, lines: int = 50) -> list[str]:
        service = self.get_service(name)
        if not service:
            return []
        return service.get_logs(lines)

    def any_running(self) -> bool:
        return any(
            svc.get_status().status == ServiceStatus.RUNNING
            for svc in self.services.values()
        )

    def all_running(self) -> bool:
        return all(
            svc.get_status().status == ServiceStatus.RUNNING
            for svc in self.services.values()
        )
