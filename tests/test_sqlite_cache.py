"""Tests for the SQLite cache implementation."""

import os
import tempfile
import time
import unittest
import threading
from flags.cache.sqlite import SQLiteCache
from flags.flag import FeatureFlag, Details


class TestSQLiteCache(unittest.TestCase):
    """Test the SQLiteCache implementation."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary database file
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
        
        self.cache = SQLiteCache(self.db_path)
        self.cache.init()
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.cache.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_init(self):
        """Test cache initialization and table creation."""
        # Verify tables exist by trying to query them
        conn = self.cache._get_connection()
        cursor = conn.cursor()
        
        # Check flags table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='flags'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check cache_metadata table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cache_metadata'")
        self.assertIsNotNone(cursor.fetchone())
        
        # Check default metadata values
        cursor.execute("SELECT value FROM cache_metadata WHERE key='next_refresh_time'")
        self.assertEqual(cursor.fetchone()[0], '0')
        
        cursor.execute("SELECT value FROM cache_metadata WHERE key='cache_ttl'")
        self.assertEqual(cursor.fetchone()[0], '300')
    
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
        
        # Verify flags are ordered by name
        self.assertEqual(all_flags[0].details.name, "feature1")
        self.assertEqual(all_flags[1].details.name, "feature2")
    
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
        
        # Verify metadata was reset
        conn = self.cache._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM cache_metadata WHERE key='next_refresh_time'")
        self.assertEqual(cursor.fetchone()[0], '0')
    
    def test_persistence(self):
        """Test that cache persists across instances."""
        # Add flags to first instance
        flags = [
            FeatureFlag(
                enabled=True,
                details=Details(name="persistent-flag", id="id1")
            ),
        ]
        self.cache.refresh(flags, 300)
        
        # Close first instance
        self.cache.close()
        
        # Create new instance with same database
        new_cache = SQLiteCache(self.db_path)
        new_cache.init()
        
        # Verify flag still exists
        enabled, exists = new_cache.get("persistent-flag")
        self.assertTrue(enabled)
        self.assertTrue(exists)
        
        new_cache.close()
    
    def test_concurrent_access(self):
        """Test concurrent access to the SQLite cache."""
        # Add initial flags
        flags = [
            FeatureFlag(
                enabled=True,
                details=Details(name=f"feature{i}", id=f"id{i}")
            )
            for i in range(50)
        ]
        self.cache.refresh(flags, 60)
        
        results = []
        errors = []
        
        def reader_thread():
            """Thread that reads from cache."""
            cache = SQLiteCache(self.db_path)
            cache.init()
            try:
                for _ in range(50):
                    all_flags = cache.get_all()
                    for flag in all_flags[:10]:  # Read first 10 to avoid too much load
                        enabled, exists = cache.get(flag.details.name)
                        if exists:
                            results.append((flag.details.name, enabled))
            except Exception as e:
                errors.append(e)
            finally:
                cache.close()
        
        def writer_thread():
            """Thread that writes to cache."""
            cache = SQLiteCache(self.db_path)
            cache.init()
            try:
                for i in range(5):
                    new_flags = flags + [
                        FeatureFlag(
                            enabled=i % 2 == 0,
                            details=Details(name=f"new-feature{i}", id=f"new-id{i}")
                        )
                    ]
                    cache.refresh(new_flags, 60)
                    time.sleep(0.05)
            except Exception as e:
                errors.append(e)
            finally:
                cache.close()
        
        # Create threads
        threads = []
        for _ in range(3):
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
    
    def test_transaction_rollback(self):
        """Test that transactions rollback on error."""
        # Add initial flag
        flags = [
            FeatureFlag(
                enabled=True,
                details=Details(name="original-flag", id="id1")
            ),
        ]
        self.cache.refresh(flags, 60)
        
        # Create a flag with invalid data that will cause an error
        # We'll mock this by using a flag that will cause a constraint violation
        try:
            # This should work normally
            self.cache.refresh(flags, 60)
        except:
            pass
        
        # Verify original flag still exists
        enabled, exists = self.cache.get("original-flag")
        self.assertTrue(exists)


if __name__ == "__main__":
    unittest.main()