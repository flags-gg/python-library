"""Main client for the Flags.gg Python library."""

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import List, Optional, Union
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .cache.cache import Cache
from .cache.memory import MemoryCache
from .cache.sqlite import SQLiteCache
from .flag import FeatureFlag


logger = logging.getLogger(__name__)


@dataclass
class Auth:
    """Authentication credentials for the Flags.gg API."""
    project_id: str
    agent_id: str
    environment_id: str


@dataclass
class Config:
    """Configuration for the Flags client."""
    base_url: str = "https://api.flags.gg"
    max_retries: int = 3
    timeout: int = 10
    auth: Optional[Auth] = None
    cache: Optional[Cache] = None
    user_agent: str = "Flags-Python"


class CircuitBreaker:
    """Simple circuit breaker implementation."""
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 10):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.is_open = False
    
    def call_succeeded(self):
        """Reset the circuit breaker on successful call."""
        self.failure_count = 0
        self.is_open = False
    
    def call_failed(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
    
    def can_attempt(self) -> bool:
        """Check if we can attempt a call."""
        if not self.is_open:
            return True
        
        # Check if recovery timeout has passed
        if time.time() - self.last_failure_time >= self.recovery_timeout:
            self.is_open = False
            self.failure_count = 0
            return True
        
        return False


class FlagResult:
    """Result wrapper for flag queries."""
    
    def __init__(self, enabled: bool):
        self._enabled = enabled
    
    def enabled(self) -> bool:
        """Check if the flag is enabled."""
        return self._enabled


class Client:
    """Main client for interacting with the Flags.gg API."""
    
    def __init__(self, config: Config):
        self.config = config
        self.cache = config.cache or SQLiteCache()
        self.circuit_breaker = CircuitBreaker(failure_threshold=1)
        
        # Initialize cache
        self.cache.init()
        
        # Setup HTTP session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=config.max_retries,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set headers
        if config.auth:
            self.session.headers.update({
                "X-Project-ID": config.auth.project_id,
                "X-Agent-ID": config.auth.agent_id,
                "X-Environment-ID": config.auth.environment_id,
                "User-Agent": config.user_agent,
                "Content-Type": "application/json",
            })
    
    def is_(self, flag_name: str) -> FlagResult:
        """
        Check if a feature flag is enabled.
        
        Args:
            flag_name: The name of the flag to check
            
        Returns:
            FlagResult that can be checked with .enabled()
        """
        # Check environment variable override first
        env_key = f"FLAGS_{flag_name.upper().replace('-', '_').replace(' ', '_')}"
        env_value = os.environ.get(env_key)
        if env_value is not None:
            enabled = env_value.lower() in ('true', '1', 'yes', 'on')
            return FlagResult(enabled)
        
        # Check if we need to refresh cache
        if self.cache.should_refresh_cache():
            self._refresh_cache()
        
        # Get from cache
        enabled, exists = self.cache.get(flag_name)
        return FlagResult(enabled)
    
    def list(self) -> List[FeatureFlag]:
        """
        Get all feature flags.
        
        Returns:
            List of all feature flags
        """
        # Check if we need to refresh cache
        if self.cache.should_refresh_cache():
            self._refresh_cache()
        
        return self.cache.get_all()
    
    def _refresh_cache(self):
        """Refresh the cache from the API."""
        if not self.circuit_breaker.can_attempt():
            logger.warning("Circuit breaker is open, using cached values")
            return
        
        try:
            # Make API request
            url = urljoin(self.config.base_url, "/flags")
            response = self.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            interval_allowed = data.get("intervalAllowed", 300)
            flags_data = data.get("flags", [])
            
            # Convert to FeatureFlag objects
            flags = [FeatureFlag.from_dict(flag_data) for flag_data in flags_data]
            
            # Update cache
            self.cache.refresh(flags, interval_allowed)
            
            # Reset circuit breaker on success
            self.circuit_breaker.call_succeeded()
            
        except Exception as e:
            logger.error(f"Failed to refresh cache: {e}")
            self.circuit_breaker.call_failed()


def new_client(**kwargs) -> Client:
    """
    Create a new Flags client with the given configuration.
    
    Args:
        base_url: Base URL for the API (default: https://api.flags.gg)
        max_retries: Maximum number of retries (default: 3)
        timeout: Request timeout in seconds (default: 10)
        project_id: Project ID for authentication
        agent_id: Agent ID for authentication
        environment_id: Environment ID for authentication
        cache: Cache implementation to use (default: SQLiteCache)
        use_memory_cache: Use in-memory cache instead of SQLite (default: False)
        
    Returns:
        Configured Client instance
    """
    config = Config()
    
    # Handle basic configuration
    if "base_url" in kwargs:
        config.base_url = kwargs["base_url"]
    if "max_retries" in kwargs:
        config.max_retries = kwargs["max_retries"]
    if "timeout" in kwargs:
        config.timeout = kwargs["timeout"]
    if "user_agent" in kwargs:
        config.user_agent = kwargs["user_agent"]
    
    # Handle authentication
    if all(k in kwargs for k in ["project_id", "agent_id", "environment_id"]):
        config.auth = Auth(
            project_id=kwargs["project_id"],
            agent_id=kwargs["agent_id"],
            environment_id=kwargs["environment_id"]
        )
    
    # Handle cache selection
    if "cache" in kwargs:
        config.cache = kwargs["cache"]
    elif kwargs.get("use_memory_cache", False):
        config.cache = MemoryCache()
    else:
        db_path = kwargs.get("sqlite_path", "/tmp/flags.db")
        config.cache = SQLiteCache(db_path)
    
    return Client(config)