"""In-memory cache implementation for the Flags.gg Python client."""

import threading
import time
from typing import Dict, List, Tuple, Optional
from .cache import Cache
from ..flag import FeatureFlag


class MemoryCache(Cache):
    """Thread-safe in-memory cache implementation."""
    
    def __init__(self):
        self._cache: Dict[str, FeatureFlag] = {}
        self._next_refresh_time: float = 0
        self._cache_ttl: int = 300  # Default 5 minutes
        self._lock = threading.RWLock()
    
    def init(self) -> None:
        """Initialize the memory cache."""
        with self._lock.write():
            self._cache.clear()
            self._next_refresh_time = 0
            self._cache_ttl = 300
    
    def get(self, name: str) -> Tuple[bool, bool]:
        """Get a single flag state from cache."""
        with self._lock.read():
            flag = self._cache.get(name)
            if flag:
                return flag.enabled, True
            return False, False
    
    def get_all(self) -> List[FeatureFlag]:
        """Get all flags from cache."""
        with self._lock.read():
            return list(self._cache.values())
    
    def refresh(self, flags: List[FeatureFlag], interval_allowed: int) -> None:
        """Refresh the cache with new flag data."""
        with self._lock.write():
            # Clear existing cache
            self._cache.clear()
            
            # Add new flags
            for flag in flags:
                self._cache[flag.details.name] = flag
            
            # Update cache metadata
            self._cache_ttl = interval_allowed
            self._next_refresh_time = time.time() + interval_allowed
    
    def should_refresh_cache(self) -> bool:
        """Check if the cache needs to be refreshed."""
        with self._lock.read():
            return time.time() >= self._next_refresh_time
    
    def clear(self) -> None:
        """Clear all cached data."""
        with self._lock.write():
            self._cache.clear()
            self._next_refresh_time = 0


class RWLock:
    """A simple readers-writer lock implementation."""
    
    def __init__(self):
        self._readers = 0
        self._writers = 0
        self._read_ready = threading.Condition(threading.RLock())
        self._write_ready = threading.Condition(threading.RLock())
    
    def read(self):
        """Context manager for read lock."""
        return _ReadLock(self)
    
    def write(self):
        """Context manager for write lock."""
        return _WriteLock(self)
    
    def acquire_read(self):
        """Acquire a read lock."""
        self._read_ready.acquire()
        while self._writers > 0:
            self._read_ready.wait()
        self._readers += 1
        self._read_ready.release()
    
    def release_read(self):
        """Release a read lock."""
        self._read_ready.acquire()
        self._readers -= 1
        if self._readers == 0:
            self._read_ready.notify_all()
        self._read_ready.release()
    
    def acquire_write(self):
        """Acquire a write lock."""
        self._write_ready.acquire()
        while self._writers > 0 or self._readers > 0:
            self._write_ready.wait()
        self._writers += 1
        self._write_ready.release()
    
    def release_write(self):
        """Release a write lock."""
        self._write_ready.acquire()
        self._writers -= 1
        self._write_ready.notify_all()
        self._write_ready.release()


class _ReadLock:
    """Context manager for read locks."""
    
    def __init__(self, rwlock):
        self._rwlock = rwlock
    
    def __enter__(self):
        self._rwlock.acquire_read()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._rwlock.release_read()


class _WriteLock:
    """Context manager for write locks."""
    
    def __init__(self, rwlock):
        self._rwlock = rwlock
    
    def __enter__(self):
        self._rwlock.acquire_write()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._rwlock.release_write()


# Update threading module to include our RWLock
threading.RWLock = RWLock