"""Token Bucket Rate Limiter for bandwidth throttling."""

import time
from threading import Lock


class TokenBucket:
    """Thread-safe Token Bucket rate limiter.
    
    Attributes:
        rate: Maximum bytes allowed per second.
        capacity: Maximum burst capacity in bytes.
    """

    def __init__(self, rate_bytes_per_sec: int, burst_seconds: float = 0.05):
        self.rate = max(1024, rate_bytes_per_sec)
        # Cap burst between 32 KB and 256 KB to prevent packet burst spikes
        burst_size = int(self.rate * burst_seconds)
        self.capacity = max(32 * 1024, min(burst_size, 256 * 1024))
        self.tokens = float(self.capacity)
        self.last_refill = time.perf_counter()
        self._lock = Lock()

    def update_rate(self, new_rate_bytes_per_sec: int) -> None:
        """Update rate dynamically while keeping current token fraction."""
        with self._lock:
            self.rate = max(1024, new_rate_bytes_per_sec)
            burst_size = int(self.rate * 0.05)
            self.capacity = max(32 * 1024, min(burst_size, 256 * 1024))
            self.tokens = min(self.tokens, float(self.capacity))

    def consume(self, packet_bytes: int) -> float:
        """Attempts to consume tokens for a packet.
        
        Returns:
            0.0 if allowed immediately.
            > 0.0 representing delay in seconds required before forwarding.
        """
        with self._lock:
            now = time.perf_counter()
            elapsed = now - self.last_refill
            self.last_refill = now

            # Refill tokens based on elapsed time
            self.tokens = min(float(self.capacity), self.tokens + elapsed * self.rate)

            if self.tokens >= packet_bytes:
                self.tokens -= packet_bytes
                return 0.0
            else:
                deficit = packet_bytes - self.tokens
                # Delay needed to accumulate the deficit tokens
                delay = deficit / self.rate
                # Deduct tokens (can go temporarily negative)
                self.tokens -= packet_bytes
                return delay
