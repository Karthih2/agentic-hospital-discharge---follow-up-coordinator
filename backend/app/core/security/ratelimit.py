import time
from collections import defaultdict, deque

from fastapi import HTTPException

_hits: dict[str, deque] = defaultdict(deque)


def limit(bucket: str, key, max_hits: int, window_sec: int) -> None:
    """Sliding window. Raises 429 when exceeded.
    ponytail: per-process memory. Move to Redis (already in the stack) when running several api workers."""
    q = _hits[f"{bucket}:{key}"]
    t = time.monotonic()
    while q and q[0] < t - window_sec:
        q.popleft()
    if len(q) >= max_hits:
        raise HTTPException(429, "Too many requests. Please try again later.")
    q.append(t)


def clear() -> None:
    _hits.clear()
