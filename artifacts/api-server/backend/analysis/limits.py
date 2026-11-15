"""Bound repeated report work without persisting identifiers or logging inputs."""
from collections import OrderedDict
from hashlib import sha256
import threading
import time
from fastapi import HTTPException

_lock = threading.Lock()
_windows = OrderedDict()


def check_analysis_rate(owner, clock=time.monotonic):
    now = clock()
    key = sha256(owner.encode()).digest()
    with _lock:
        for expired in [k for k, v in _windows.items() if v[-1] <= now - 60]:
            del _windows[expired]
        times = [x for x in _windows.pop(key, []) if x > now - 60]
        if len(times) >= 6:
            _windows[key] = times
            raise HTTPException(429, "Please wait before generating another farming report.",
                                headers={"Retry-After": "60"})
        if len(_windows) >= 4096:
            raise HTTPException(429, "Report service is busy. Please retry shortly.",
                                headers={"Retry-After": "60"})
        _windows[key] = [*times, now]
