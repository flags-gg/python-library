"""Tests for the memory cache implementation."""

import time
import unittest
import threading
from flags.cache.memory import MemoryCache
from flags.flag import FeatureFlag, Details


class TestMemoryCache(unittest.TestCase):
    """Test the MemoryCache implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.cache = MemoryCache()
        self.cache.init()
    
    def test_init(self):
        """Test cache initialization."""
        self.assertEqual(len(self.cache._cache), 0)
        self.assertEqual(self.cache._next_refresh_time, 0)
        self.assertEqual(self.cache._cache_ttl, 300)
    
    def test_get_nonexistent(self):
        """Test getting a non-existent flag."""
        enabled, exists = self.cache.get("nonexistent")
        self.assertFalse(enabled)
        self.assertFalse(exists)
    
    def test_refresh_and_get(self):
        """Test refreshing cache and getting flags."""
        # Create test flags
        flags = [
            FeatureFlag(
                enabled=True,
                details=Details(name="feature1", id="id1")
            ),
            FeatureFlag(
                enabled=False,
                details=Details(name="feature2", id="id2")
            ),
        ]
        
        # Refresh cache
        self.cache.refresh(flags, 60)
        
        # Test getting individual flags
        enabled, exists = self.cache.get("feature1")
        self.assertTrue(enabled)
        self.assertTrue(exists)
        
        enabled, exists = self.cache.get("feature2")
        self.assertFalse(enabled)
        self.assertTrue(exists)
    
    def test_get_all(self):
        """Test getting all flags from cache."""
        # Create test flags
        flags = [
            FeatureFlag(
                enabled=True,
                details=Details(name="feature1", id="id1")
            ),
            FeatureFlag(
                enabled=False,
                details=Details(name="feature2", id="id2")
            ),
        ]
        
        # Refresh cache
        self.cache.refresh(flags, 60)
        
        # Get all flags
        all_flags = self.cache.get_all()
        self.assertEqual(len(all_flags), 2)
        
        # Verify flags
        flag_names = {flag.details.name for flag in all_flags}
        self.assertEqual(flag_names, {"feature1", "feature2"})
    
    def test_should_refresh_cache(self):
        """Test cache refresh timing."""
        # Initially should refresh
        self.assertTrue(self.cache.should_refresh_cache())
        
        # Refresh with 1 second TTL
        flags = [
            FeatureFlag(
                enabled=True,
                details=Details(name="feature1", id="id1")
            ),
        ]
        self.cache.refresh(flags, 1)
        
        # Should not refresh immediately
        self.assertFalse(self.cache.should_refresh_cache())
        
        # Wait for TTL to expire
        time.sleep(1.1)
        self.assertTrue(self.cache.should_refresh_cache())
    
    def test_clear(self):
        """Test clearing the cache."""
        # Add some flags
        flags = [
            FeatureFlag(
                enabled=True,
                details=Details(name="feature1", id="id1")
            ),
        ]
        self.cache.refresh(flags, 60)
        
        # Verify flag exists
        enabled, exists = self.cache.get("feature1")
        self.assertTrue(exists)
        
        # Clear cache
        self.cache.clear()
        
        # Verify cache is empty
        enabled, exists = self.cache.get("feature1")
        self.assertFalse(exists)
        self.assertEqual(self.cache._next_refresh_time, 0)
    
    def test_concurrent_access(self):
        """Test concurrent access to the cache."""
        # Add initial flags
        flags = [
            FeatureFlag(
                enabled=True,
                details=Details(name=f"feature{i}", id=f"id{i}")
            )
            for i in range(100)
        ]
        self.cache.refresh(flags, 60)
        
        results = []
        errors = []
        
        def reader_thread():
            """Thread that reads from cache."""
            try:
                for _ in range(100):
                    all_flags = self.cache.get_all()
                    for flag in all_flags:
                        enabled, exists = self.cache.get(flag.details.name)
                        if exists:
                            results.append((flag.details.name, enabled))
            except Exception as e:
                errors.append(e)
        
        def writer_thread():
            """Thread that writes to cache."""
            try:
                for i in range(10):
                    new_flags = [
                        FeatureFlag(
                            enabled=i % 2 == 0,
                            details=Details(name=f"new-feature{i}", id=f"new-id{i}")
                        )
                    ]
                    self.cache.refresh(flags + new_flags, 60)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(e)
        
        # Create threads
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=reader_thread))
            threads.append(threading.Thread(target=writer_thread))
        
        # Start threads
        for thread in threads:
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Check for errors
        self.assertEqual(len(errors), 0, f"Concurrent access errors: {errors}")
        self.assertGreater(len(results), 0, "No results from concurrent reads")


if __name__ == "__main__":
    unittest.main()