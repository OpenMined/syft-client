import threading
import time
from abc import ABC, abstractmethod
from typing import Optional


class Monitor(ABC):
    @abstractmethod
    def _check_all_entities(self):
        pass

    def check(self, interval: Optional[int] = None, duration: Optional[int] = None):
        if interval is None:
            self._check_all_entities()
            return

        start_time = time.time()
        print(f"🔍 {self.__class__.__name__} started (interval: {interval}s)")

        try:
            while True:
                self._check_all_entities()

                if duration is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= duration:
                        print(f"✅ Monitoring completed ({elapsed:.0f}s)")
                        break

                time.sleep(interval)

        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            print(f"\n⏹️  Monitoring stopped ({elapsed:.0f}s elapsed)")

    def start(self, interval: int = 10) -> threading.Thread:
        self._stop_event = threading.Event()

        def run():
            print(f"🔍 {self.__class__.__name__} started (interval: {interval}s)")
            while not self._stop_event.is_set():
                try:
                    self._check_all_entities()
                except Exception as e:
                    print(f"⚠️  {self.__class__.__name__} error: {e}")
                self._stop_event.wait(interval)
            print(f"⏹️  {self.__class__.__name__} stopped")

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread

    def stop(self):
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
