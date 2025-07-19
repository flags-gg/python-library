"""Tests for the main Flags client."""

import json
import os
import tempfile
import time
import unittest
from unittest.mock import Mock, patch, MagicMock
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from flags import new_client, Client, Auth, Config, MemoryCache, SQLiteCache
from flags.flag import FeatureFlag, Details


class MockFlagsHandler(BaseHTTPRequestHandler):
    """Mock HTTP handler for testing."""
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/flags":
            # Check headers
            if (self.headers.get("X-Project-ID") == "test-project" and
                self.headers.get("X-Agent-ID") == "test-agent" and
                self.headers.get("X-Environment-ID") == "test-env"):
                
                response = {
                    "intervalAllowed": 60,
                    "flags": [
                        {
                            "enabled": True,
                            "details": {
                                "name": "feature1",
                                "id": "id1"
                            }
                        },
                        {
                            "enabled": False,
                            "details": {
                                "name": "feature2",
                                "id": "id2"
                            }
                        }
                    ]
                }
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(401)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress log messages during tests."""
        pass


class TestClient(unittest.TestCase):
    """Test the main Client class."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test server."""
        cls.server = HTTPServer(("localhost", 0), MockFlagsHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever)
        cls.server_thread.daemon = True
        cls.server_thread.start()
        cls.base_url = f"http://localhost:{cls.server.server_port}"
    
    @classmethod
    def tearDownClass(cls):
        """Shut down test server."""
        cls.server.shutdown()
        cls.server_thread.join()
    
    def setUp(self):
        """Set up test fixtures."""
        # Clear any environment variables
        for key in list(os.environ.keys()):
            if key.startswith("FLAGS_"):
                del os.environ[key]
        
        # Create temp file for SQLite tests
        self.temp_file = tempfile.NamedTemporaryFile(delete=False)
        self.db_path = self.temp_file.name
        self.temp_file.close()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)
    
    def test_new_client_defaults(self):
        """Test creating a client with default settings."""
        client = new_client()
        
        self.assertIsInstance(client, Client)
        self.assertEqual(client.config.base_url, "https://api.flags.gg")
        self.assertEqual(client.config.max_retries, 3)
        self.assertEqual(client.config.timeout, 10)
        self.assertIsInstance(client.cache, SQLiteCache)
    
    def test_new_client_with_options(self):
        """Test creating a client with custom options."""
        client = new_client(
            base_url="https://custom.url",
            max_retries=5,
            timeout=30,
            project_id="proj",
            agent_id="agent",
            environment_id="env",
            use_memory_cache=True
        )
        
        self.assertEqual(client.config.base_url, "https://custom.url")
        self.assertEqual(client.config.max_retries, 5)
        self.assertEqual(client.config.timeout, 30)
        self.assertIsNotNone(client.config.auth)
        self.assertEqual(client.config.auth.project_id, "proj")
        self.assertIsInstance(client.cache, MemoryCache)
    
    def test_is_with_environment_override(self):
        """Test flag checking with environment variable override."""
        # Set environment variable
        os.environ["FLAGS_TEST_FEATURE"] = "true"
        
        client = new_client()
        result = client.is_("test-feature")
        
        self.assertTrue(result.enabled())
        
        # Test with different variations
        os.environ["FLAGS_TEST_FEATURE"] = "false"
        result = client.is_("test-feature")
        self.assertFalse(result.enabled())
        
        os.environ["FLAGS_TEST_WITH_SPACES"] = "yes"
        result = client.is_("test with spaces")
        self.assertTrue(result.enabled())
    
    def test_is_with_api_call(self):
        """Test flag checking with API call."""
        client = new_client(
            base_url=self.base_url,
            project_id="test-project",
            agent_id="test-agent",
            environment_id="test-env",
            use_memory_cache=True
        )
        
        # First call should hit the API
        result = client.is_("feature1")
        self.assertTrue(result.enabled())
        
        result = client.is_("feature2")
        self.assertFalse(result.enabled())
        
        # Subsequent calls should use cache
        result = client.is_("feature1")
        self.assertTrue(result.enabled())
    
    def test_list(self):
        """Test listing all flags."""
        client = new_client(
            base_url=self.base_url,
            project_id="test-project",
            agent_id="test-agent",
            environment_id="test-env",
            use_memory_cache=True
        )
        
        flags = client.list()
        
        self.assertEqual(len(flags), 2)
        self.assertEqual(flags[0].details.name, "feature1")
        self.assertTrue(flags[0].enabled)
        self.assertEqual(flags[1].details.name, "feature2")
        self.assertFalse(flags[1].enabled)
    
    def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        # Create client with invalid URL
        client = new_client(
            base_url="http://localhost:9999",  # Non-existent server
            project_id="test-project",
            agent_id="test-agent",
            environment_id="test-env",
            max_retries=2,
            timeout=1,
            use_memory_cache=True
        )
        
        # First call should fail and open circuit
        result = client.is_("test-flag")
        self.assertFalse(result.enabled())
        
        # Circuit should be open
        self.assertTrue(client.circuit_breaker.is_open)
        
        # Subsequent calls should not attempt API
        result = client.is_("test-flag")
        self.assertFalse(result.enabled())
    
    def test_cache_persistence_with_sqlite(self):
        """Test that SQLite cache persists across client instances."""
        # First client
        client1 = new_client(
            base_url=self.base_url,
            project_id="test-project",
            agent_id="test-agent",
            environment_id="test-env",
            sqlite_path=self.db_path
        )
        
        # Populate cache
        flags = client1.list()
        self.assertEqual(len(flags), 2)
        
        # Second client with same database
        client2 = new_client(
            base_url="http://invalid",  # Invalid URL to ensure we use cache
            sqlite_path=self.db_path
        )
        
        # Should get flags from persisted cache
        result = client2.is_("feature1")
        self.assertTrue(result.enabled())
    
    def test_cache_ttl_refresh(self):
        """Test cache TTL and refresh behavior."""
        client = new_client(
            base_url=self.base_url,
            project_id="test-project",
            agent_id="test-agent",
            environment_id="test-env",
            use_memory_cache=True
        )
        
        # Initial fetch
        result = client.is_("feature1")
        self.assertTrue(result.enabled())
        
        # Cache should not need refresh immediately
        self.assertFalse(client.cache.should_refresh_cache())
        
        # Manually expire cache
        client.cache._next_refresh_time = time.time() - 1
        
        # Cache should need refresh now
        self.assertTrue(client.cache.should_refresh_cache())
        
        # Next call should trigger refresh
        result = client.is_("feature1")
        self.assertTrue(result.enabled())
    
    def test_auth_headers(self):
        """Test that authentication headers are properly set."""
        client = new_client(
            base_url=self.base_url,
            project_id="test-project",
            agent_id="test-agent",
            environment_id="test-env",
            use_memory_cache=True
        )
        
        # Headers should be set in session
        self.assertEqual(client.session.headers["X-Project-ID"], "test-project")
        self.assertEqual(client.session.headers["X-Agent-ID"], "test-agent")
        self.assertEqual(client.session.headers["X-Environment-ID"], "test-env")
        self.assertEqual(client.session.headers["User-Agent"], "Flags-Python")
        self.assertEqual(client.session.headers["Content-Type"], "application/json")
    
    def test_custom_user_agent(self):
        """Test setting a custom user agent."""
        client = new_client(
            user_agent="MyApp/1.0",
            use_memory_cache=True
        )
        
        self.assertEqual(client.config.user_agent, "MyApp/1.0")


class TestFlagResult(unittest.TestCase):
    """Test the FlagResult class."""
    
    def test_enabled_method(self):
        """Test the enabled() method."""
        from flags.client import FlagResult
        
        result_true = FlagResult(True)
        self.assertTrue(result_true.enabled())
        
        result_false = FlagResult(False)
        self.assertFalse(result_false.enabled())


if __name__ == "__main__":
    unittest.main()