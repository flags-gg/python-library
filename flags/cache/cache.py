"""Cache interface and system for the Flags.gg Python client."""

from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from ..flag import FeatureFlag


class Cache(ABC):
    """Abstract base class for cache implementations."""
    
    @abstractmethod
    def init(self) -> None:
        """Initialize the cache system."""
        pass
    
    @abstractmethod
    def get(self, name: str) -> Tuple[bool, bool]:
        """
        Get a single flag state from cache.
        
        Args:
            name: The flag name to retrieve
            
        Returns:
            Tuple of (enabled, exists) where exists indicates if the flag was found
        """
        pass
    
    @abstractmethod
    def get_all(self) -> List[FeatureFlag]:
        """
        Get all flags from cache.
        
        Returns:
            List of all cached feature flags
        """
        pass
    
    @abstractmethod
    def refresh(self, flags: List[FeatureFlag], interval_allowed: int) -> None:
        """
        Refresh the cache with new flag data.
        
        Args:
            flags: List of feature flags to cache
            interval_allowed: TTL in seconds for the cache
        """
        pass
    
    @abstractmethod
    def should_refresh_cache(self) -> bool:
        """
        Check if the cache needs to be refreshed.
        
        Returns:
            True if cache should be refreshed, False otherwise
        """
        pass
    
    @abstractmethod
    def clear(self) -> None:
        """Clear all cached data."""
        pass