"""Flags.gg Python client library."""

from .client import Client, new_client, Auth, Config
from .flag import FeatureFlag, Details
from .cache.cache import Cache
from .cache.memory import MemoryCache
from .cache.sqlite import SQLiteCache

__version__ = "1.0.0"
__all__ = [
    "Client",
    "new_client",
    "Auth",
    "Config",
    "FeatureFlag",
    "Details",
    "Cache",
    "MemoryCache",
    "SQLiteCache",
]