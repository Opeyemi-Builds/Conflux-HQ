"""Client-side sliding-window rate guard for the shared 60 req/min budget.

Forge allows 60 requests/minute/team shared across Bank API and MaaS. This
guard keeps the MaaS slice from burning the budget; Adfola's Bank slice owns
its own share. When the budget is exhausted the caller falls back instead of
queuing a model call on a dashboard read.
"""

import threading
import time
from collections import deque


class RateLimitExceeded(Exception):
    pass


class MaasRateLimiter:
    def __init__(self, per_minute: int = 60):
        self._limit = max(1, per_minute)
        self._hits: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        now = time.monotonic()
        with self._lock:
            while self._hits and self._hits[0] <= now - 60.0:
                self._hits.popleft()
            if len(self._hits) >= self._limit:
                raise RateLimitExceeded(f"maas budget exhausted ({self._limit}/min)")
            self._hits.append(now)

    @property
    def remaining(self) -> int:
        now = time.monotonic()
        with self._lock:
            while self._hits and self._hits[0] <= now - 60.0:
                self._hits.popleft()
            return max(0, self._limit - len(self._hits))


_limiter: MaasRateLimiter | None = None
_limiter_lock = threading.Lock()


def get_limiter(per_minute: int = 60) -> MaasRateLimiter:
    global _limiter
    with _limiter_lock:
        if _limiter is None or _limiter._limit != per_minute:
            _limiter = MaasRateLimiter(per_minute)
        return _limiter
