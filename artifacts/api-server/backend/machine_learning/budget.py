"""Process-wide bounded research acquisition; never silently finishes partial data."""
import threading
import time
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class ResearchBudget:
    def __init__(self, root, *, seconds=2700, max_bytes=1_610_612_736):
        self.root = Path(root)
        self.started = time.monotonic()
        self.seconds = seconds
        self.max_bytes = max_bytes
        self.lock = threading.Lock()

    def check(self):
        # At most two cells are in flight. Per-download byte limits bound the
        # possible overshoot; this is checked again after each completed cell.
        with self.lock:
            elapsed = time.monotonic() - self.started
            size = sum(p.stat().st_size for p in self.root.rglob("*") if p.is_file())
            if elapsed >= self.seconds:
                raise BudgetExceeded("research_time_budget_exceeded")
            if size >= self.max_bytes:
                raise BudgetExceeded("research_cache_budget_exceeded")
            return {"elapsed_seconds": elapsed, "cache_bytes": size,
                    "maximum_seconds": self.seconds, "maximum_bytes": self.max_bytes}
