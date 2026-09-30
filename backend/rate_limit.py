"""
Per-IP rate limiting for the expensive, public endpoints.

The backend runs --allow-unauthenticated, so AI review, document/knowledge/form
uploads and generation are reachable by anyone. These sliding-window limits cap
the cost/DoS blast radius per client IP.

Applied as FastAPI dependencies, not middleware, on purpose: BaseHTTPMiddleware
buffers the response and would break the SSE/streaming endpoints
(/chat/stream, /stream/{id}). A dependency runs before the handler and never
touches the response body, so streaming is unaffected. The 429 it raises still
gets CORS headers, because CORSMiddleware wraps every response including errors.

Caveat: counters live in this process. With several Cloud Run instances the
effective cap is (limit x instances); --session-affinity keeps a client on one
instance so per-client limits hold in normal use. For a hard global cap, back
the counters with Redis/Firestore.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable, Deque, Dict, Tuple

from fastapi import HTTPException, Request

from config import settings


def _client_ip(request: Request) -> str:
    # On Cloud Run the direct caller is the Google Front End, so request.client
    # is useless; the real client is the first hop of X-Forwarded-For.
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


class _SlidingWindow:
    """Per-(bucket, ip) request timestamps within a window.

    Touched only from the asyncio event loop (no await between read and write),
    so it needs no lock.
    """

    def __init__(self) -> None:
        self._hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._last_prune = 0.0

    def hit(self, bucket: str, ip: str, limit: int, window: float) -> Tuple[bool, int]:
        """Record a hit. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        # Prune BEFORE fetching this client's deque. Pruning drops empty deques,
        # so if it ran after the fetch it could delete the very deque we hold a
        # reference to, losing this hit (an off-by-one in the limit).
        self._prune(now)
        dq = self._hits[(bucket, ip)]
        cutoff = now - window
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            retry_after = int(window - (now - dq[0])) + 1
            return False, max(retry_after, 1)
        dq.append(now)
        return True, 0

    def _prune(self, now: float) -> None:
        # Drop emptied deques periodically so an IP flood can't grow memory
        # without bound.
        if now - self._last_prune < 60:
            return
        self._last_prune = now
        for key in [k for k, dq in self._hits.items() if not dq]:
            del self._hits[key]


_window = _SlidingWindow()


def rate_limit(bucket: str, limit_attr: str) -> Callable:
    """Build a dependency limiting `bucket` to settings.<limit_attr> requests
    per settings.RATELIMIT_WINDOW_SECONDS, per client IP."""

    async def _dep(request: Request) -> None:
        if not settings.RATELIMIT_ENABLED:
            return
        limit = int(getattr(settings, limit_attr))
        window = float(settings.RATELIMIT_WINDOW_SECONDS)
        allowed, retry_after = _window.hit(bucket, _client_ip(request), limit, window)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit reached for {bucket}. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

    return _dep


review_rate_limit = rate_limit("review", "RATELIMIT_REVIEW")
generate_rate_limit = rate_limit("generate", "RATELIMIT_GENERATE")
upload_rate_limit = rate_limit("upload", "RATELIMIT_UPLOAD")
